#!/usr/bin/env python3
"""Interactive 3D event display for Muon Collider edm4hep files.

Reads one event from a ddsim / digi / reco edm4hep ROOT file (via podio)
and writes a single self-contained HTML file: a WebGL point cloud with
drag-rotate / zoom / pan, per-subsystem toggles, an energy threshold
slider, and click-to-inspect. Calorimeter hits are drawn at their
physical cell size, so zooming in reveals the actual detector
granularity (ECAL 5.1 mm cells, HCAL 30 mm cells); detector envelopes
are drawn from the data itself (per-subsystem hit extents).

Run INSIDE the mucoll-sim container (needs podio), e.g.:

  shifter --image=ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:v3.0 \
      /bin/bash -c 'source /opt/setup_mucoll.sh && \
      python3 scripts/event_display_3d.py reco.edm4hep.root -e 0 -o ev0.html'

Open the HTML in any browser - no server, no network needed.

Matt LeBlanc, Brown University 2026
"""

import argparse
import json
import math
import os
import sys

# Subsystem styling: (key, display name, color, cell size [mm], kind)
# Colors are the first three slots of a CVD-validated dark-mode categorical
# palette (ECAL/HCAL/muon); tracker hits are neutral ink, not a series hue.
SUBSYSTEMS = [
    ("ecal",    "ECAL",         "#d95926",  5.1, "cells"),
    ("hcal",    "HCAL",         "#3987e5", 30.0, "cells"),
    ("muon",    "Muon system",  "#199e70", 30.0, "cells"),
    ("ocal",    "Other calo",   "#9085e9", 10.0, "cells"),
    ("tracker", "Tracker hits", "#c3c2b7",  3.0, "points"),
]
RAY_MC, RAY_PFO = "#6a6a63", "#d55181"


def classify(name, typename):
    n = name.lower()
    if "Link" in typename or "Association" in typename:
        return None     # hit <-> MC truth link collections, not hits
    if "TrackerHit" in typename:
        return "tracker"
    if "CalorimeterHit" in typename:
        if "ecal" in n:
            return "ecal"
        if "hcal" in n:
            return "hcal"
        if "yoke" in n or "muon" in n:
            return "muon"
        return "ocal"
    return None


_CALO_STAGES = {"Rec": 5, "": 4, "Digi": 3, "Sel": 2, "Coned": 1}


def select_collections(names_types):
    """Pick ONE digitization stage per subsystem so hits are not drawn
    multiple times. Reco files carry the Sim collections plus every digi
    stage (Coned/Digi/Rec/Sel) of the same cells: prefer the calibrated
    'Rec' calo collections and the merged digitized tracker hits, and
    fall back to sim-level collections only when nothing digitized exists.
    """
    digi_calo, sim_calo, digi_trk, sim_trk, selected = {}, [], [], [], []
    for name, tname in names_types:
        if "Link" in tname or "Association" in tname:
            continue
        if tname == "SimCalorimeterHit":
            sim_calo.append(name)
        elif "CalorimeterHit" in tname:
            base, stage = name, ""
            for s in ("Coned", "Digi", "Rec", "Sel"):
                if name.endswith(s):
                    base, stage = name[: -len(s)], s
            prev = digi_calo.get(base)
            if prev is None or _CALO_STAGES[stage] > _CALO_STAGES[prev[1]]:
                digi_calo[base] = (name, stage)
        elif tname == "SimTrackerHit":
            sim_trk.append(name)
        elif "TrackerHit" in tname:
            digi_trk.append(name)
    selected += [n for n, _ in digi_calo.values()] or sim_calo
    if "MergedTrackerHits" in digi_trk:
        selected += ["MergedTrackerHits"]   # union of the per-system digi hits
    else:
        selected += digi_trk or sim_trk
    return set(selected)


def extract(path, ievent, pmin):
    from podio.root_io import Reader

    frames = Reader(path).get("events")
    if ievent >= len(frames):
        sys.exit(f"Event {ievent} not found ({len(frames)} events in {path})")
    frame = frames[ievent]

    names_types = []
    for name in frame.getAvailableCollections():
        coll = frame.get(name)
        if len(coll):
            names_types.append((name, type(coll[0]).__name__))
    keep = select_collections(names_types)

    hits = {k: [] for k, *_ in SUBSYSTEMS}   # (E, x, y, z)
    colls_used = []
    mc_rays, pfo_rays, rp_colls = [], [], {}
    npfo, epfo = 0, 0.0

    for name, tname in names_types:
        coll = frame.get(name)
        key = classify(name, tname) if name in keep else None
        if key:
            for h in coll:
                pos = h.getPosition()
                try:
                    e = h.getEnergy()
                except AttributeError:
                    try:
                        e = h.getEDep()
                    except AttributeError:
                        e = 0.0
                hits[key].append((e, pos.x, pos.y, pos.z))
            colls_used.append((name, tname, len(coll)))
        elif tname.startswith("MCParticle"):
            for mc in coll:
                if mc.getGeneratorStatus() != 1:
                    continue
                mom = mc.getMomentum()
                p = math.sqrt(mom.x**2 + mom.y**2 + mom.z**2)
                if p > pmin and abs(mc.getPDG()) not in (12, 14, 16):
                    mc_rays.append((mom.x / p, mom.y / p, mom.z / p, p))
        elif tname.startswith("ReconstructedParticle"):
            rp_colls[name] = coll

    # several ReconstructedParticle collections coexist (PandoraPFOs,
    # UsedPFOs, JetOut, ...) and overlap -- draw exactly one
    rp_name = ("PandoraPFOs" if "PandoraPFOs" in rp_colls
               else sorted(rp_colls)[0] if rp_colls else None)
    if rp_name:
        for pf in rp_colls[rp_name]:
            mom = pf.getMomentum()
            p = math.sqrt(mom.x**2 + mom.y**2 + mom.z**2)
            npfo += 1
            epfo += pf.getEnergy()
            if p > pmin:
                pfo_rays.append((mom.x / p, mom.y / p, mom.z / p, pf.getEnergy()))

    # build JSON groups: hits sorted by E desc (threshold slider relies on it)
    groups, env = [], []
    for key, label, color, cell, kind in SUBSYSTEMS:
        hh = sorted(hits[key], reverse=True)
        if not hh:
            continue
        xyz, es = [], []
        for e, x, y, z in hh:
            xyz += [round(x, 1), round(y, 1), round(z, 1)]
            es.append(float(f"{e:.3g}"))
        groups.append({"name": label, "color": color, "cell": cell, "kind": kind,
                       "xyz": xyz, "e": es, "esum": round(sum(es), 2)})
        if kind == "cells":
            rr = [math.hypot(x, y) for _, x, y, _ in hh]
            env.append({"color": color, "rin": round(min(rr)), "rout": round(max(rr)),
                        "zmax": round(max(abs(z) for *_, z in hh))})

    def rays(lst, scale):
        out = []
        for ux, uy, uz, w in lst:
            L = scale * math.log10(w / pmin + 1.0)
            out += [0, 0, 0, round(L * ux, 1), round(L * uy, 1), round(L * uz, 1)]
        return out

    rmax = max((e["rout"] for e in env), default=2000) / 3.5
    ray_sets = []
    if pfo_rays:
        ray_sets.append({"name": "PFO rays (len ~ log E)", "color": RAY_PFO,
                         "on": True, "xyz": rays(pfo_rays, rmax)})
    if mc_rays:
        ray_sets.append({"name": "MC truth rays", "color": RAY_MC,
                         "on": not pfo_rays, "xyz": rays(mc_rays, rmax)})

    ecalo = sum(g["esum"] for g in groups if g["kind"] == "cells")
    nhits = sum(g["xyz"].__len__() // 3 for g in groups)
    stats = [["calo hits E sum", f"{ecalo:.1f} GeV"],
             ["hits drawn", f"{nhits}"]]
    if npfo:
        stats += [[rp_name, f"{npfo}"], [f"{rp_name} E sum", f"{epfo:.1f} GeV"]]
    stats += [["MC stable (p>%g GeV)" % pmin, f"{len(mc_rays)}"]]

    meta = {"title": "MAIA Event Viewer",
            "file": os.path.basename(path), "event": ievent, "stats": stats}
    for name, tname, nn in sorted(colls_used):
        print(f"  {name:42s} {tname:28s} n={nn}")
    for k, v in stats:
        print(f"  {k}: {v}")
    return {"meta": meta, "groups": groups, "rays": ray_sets, "env": env}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", help="edm4hep .root file (sim, digi or reco)")
    ap.add_argument("-e", "--event", type=int, default=0)
    ap.add_argument("-o", "--output", default=None, help="output HTML")
    ap.add_argument("--pmin", type=float, default=1.0,
                    help="min momentum for MC/PFO rays [GeV]")
    args = ap.parse_args()

    data = extract(args.input, args.event, args.pmin)
    tmpl = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "event_display_3d_template.html")
    with open(tmpl) as f:
        html = f.read()
    html = html.replace("/*EVENT_JSON*/null",
                        json.dumps(data, separators=(",", ":")))
    # standards mode when opened directly from disk
    html = "<!doctype html>\n<meta charset='utf-8'>\n" + html
    out = args.output or (
        os.path.splitext(os.path.basename(args.input))[0]
        + f"_ev{args.event}_3d.html")
    with open(out, "w") as f:
        f.write(html)
    print(f"wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
