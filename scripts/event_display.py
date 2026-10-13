#!/usr/bin/env python3
"""Simple event display for Muon Collider production files.

Draws an x-y (transverse) and z-R (longitudinal, R signed by the y
coordinate) view of one event. Works on two kinds of input:

  * HepMC3 ASCII from Whizard (*.hepmc): final-state particles drawn as
    momentum rays from the origin, length ~ log(p), colored by species.
  * edm4hep ROOT files from ddsim / digi / reco (*.root, read via podio):
    tracker hits as points, calorimeter hits as points sized by energy,
    with MCParticle momentum rays overlaid for generator-stable particles.

Run INSIDE the mucoll-sim container (needs podio + matplotlib), e.g.:

  shifter --image=ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:v3.0 \
      /bin/bash -c 'source /opt/setup_mucoll.sh && \
      python3 scripts/event_display.py reco.edm4hep.root -e 0 -o ev0.png'

  python3 scripts/event_display.py mumu_z_hadrons_10TeV.hepmc -e 3

Matt LeBlanc, Brown University 2026
"""

import argparse
import math
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------------------------
# Particle categories for generator-level displays
# ---------------------------------------------------------------------------
CATEGORIES = [
    ("photon",         "#f1a208", lambda pdg, q: pdg == 22),
    ("e/mu",           "#0b6e4f", lambda pdg, q: abs(pdg) in (11, 13)),
    ("neutrino",       "#bbbbbb", lambda pdg, q: abs(pdg) in (12, 14, 16)),
    ("charged hadron", "#1f77b4", lambda pdg, q: q != 0),
    ("neutral hadron", "#d62728", lambda pdg, q: True),
]

# Minimal charge lookup good enough for classification (hadrons w/ charge
# from PDG numbering: last digits; fall back to "neutral").
_CHARGED = {211, 321, 2212, 213, 323, 411, 431, 521, 541, 3222, 3112, 3312, 3334}


def _charge(pdg):
    if abs(pdg) in (11, 13, 15):
        return -1 if pdg > 0 else 1
    if abs(pdg) in _CHARGED:
        return 1 if pdg > 0 else -1
    return 0


def _category(pdg):
    q = _charge(pdg)
    for name, color, match in CATEGORIES:
        if match(pdg, q):
            return name, color
    return "other", "#999999"


# ---------------------------------------------------------------------------
# HepMC3 ASCII input
# ---------------------------------------------------------------------------
def read_hepmc_event(path, ievent):
    """Return a list of (pdg, px, py, pz, E) for status-1 particles."""
    n = -1
    particles = None
    with open(path) as f:
        for line in f:
            tok = line.split()
            if not tok:
                continue
            if tok[0] == "E":
                if n == ievent:
                    return particles
                n += 1
                particles = [] if n == ievent else None
            elif tok[0] == "P" and particles is not None:
                pdg = int(tok[3])
                px, py, pz, E = map(float, tok[4:8])
                status = int(tok[9])
                if status == 1:
                    particles.append((pdg, px, py, pz, E))
    if n == ievent and particles is not None:
        return particles
    raise SystemExit(f"Event {ievent} not found in {path} (file has {n + 1})")


def display_hepmc(path, ievent, outfile, pmin):
    parts = read_hepmc_event(path, ievent)
    fig, (axy, azr) = plt.subplots(1, 2, figsize=(13, 6.2))

    seen = set()
    esum = 0.0
    for pdg, px, py, pz, E in parts:
        esum += E
        p = math.sqrt(px * px + py * py + pz * pz)
        if p < pmin:
            continue
        name, color = _category(pdg)
        # ray length ~ log of momentum so TeV and GeV tracks share a canvas
        length = math.log10(p / pmin + 1.0)
        label = name if name not in seen else None
        seen.add(name)
        pt = math.hypot(px, py)
        if pt > 0:
            axy.plot([0, length * px / p], [0, length * py / p],
                     color=color, lw=0.8, alpha=0.75, label=label)
        rsign = 1.0 if py >= 0 else -1.0
        azr.plot([0, length * pz / p], [0, length * rsign * pt / p],
                 color=color, lw=0.8, alpha=0.75)

    for ax, xl, yl in ((axy, "x direction", "y direction"),
                       (azr, "z direction", "R direction (sign of y)")):
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.set_aspect("equal")
        ax.axhline(0, color="k", lw=0.3)
        ax.axvline(0, color="k", lw=0.3)
    axy.legend(loc="upper right", fontsize=8)
    fig.suptitle(
        f"{os.path.basename(path)}  event {ievent}  "
        f"(generator level, {len(parts)} final-state particles, "
        f"sum E = {esum:.0f} GeV; ray length ~ log p, p > {pmin} GeV)"
    )
    fig.tight_layout()
    fig.savefig(outfile, dpi=160)
    print(f"wrote {outfile}")


# ---------------------------------------------------------------------------
# edm4hep (podio) input
# ---------------------------------------------------------------------------
def display_edm4hep(path, ievent, outfile, pmin):
    from podio.root_io import Reader

    reader = Reader(path)
    frames = reader.get("events")
    nev = len(frames)
    if ievent >= nev:
        raise SystemExit(f"Event {ievent} not found in {path} (file has {nev})")
    frame = frames[ievent]

    trk_xyz = []          # tracker hits
    cal = []              # (x, y, z, energy) calo hits
    rays = []             # MCParticle momentum rays
    counts = {}

    for name in frame.getAvailableCollections():
        coll = frame.get(name)
        if len(coll) == 0:
            continue
        tname = type(coll[0]).__name__
        counts[name] = (tname, len(coll))
        if "TrackerHit" in tname:
            for h in coll:
                pos = h.getPosition()
                trk_xyz.append((pos.x, pos.y, pos.z))
        elif "CalorimeterHit" in tname:
            for h in coll:
                pos = h.getPosition()
                cal.append((pos.x, pos.y, pos.z, h.getEnergy()))
        elif tname.startswith("MCParticle"):
            for mc in coll:
                if mc.getGeneratorStatus() != 1:
                    continue
                mom = mc.getMomentum()
                p = math.sqrt(mom.x**2 + mom.y**2 + mom.z**2)
                if p > pmin:
                    rays.append((mc.getPDG(), mom.x, mom.y, mom.z, p))

    trk = np.array(trk_xyz) if trk_xyz else np.empty((0, 3))
    cal = np.array(cal) if cal else np.empty((0, 4))

    fig, (axy, azr) = plt.subplots(1, 2, figsize=(14, 6.6))

    # Scale for MC rays: reach the outer edge of whatever hits exist
    rmax = 2000.0
    if len(cal):
        rmax = max(rmax, np.hypot(cal[:, 0], cal[:, 1]).max())

    for pdg, px, py, pz, p in rays:
        name, color = _category(pdg)
        if name == "neutrino":
            continue
        length = rmax * math.log10(p / pmin + 1.0) / 4.0
        pt = math.hypot(px, py)
        axy.plot([0, length * px / p], [0, length * py / p],
                 color=color, lw=0.5, alpha=0.4, zorder=1)
        rsign = 1.0 if py >= 0 else -1.0
        azr.plot([0, length * pz / p], [0, length * rsign * pt / p],
                 color=color, lw=0.5, alpha=0.4, zorder=1)

    if len(cal):
        esz = 4.0 * np.sqrt(cal[:, 3] / max(cal[:, 3].max(), 1e-9)) * 20 + 0.3
        csign = np.where(cal[:, 1] >= 0, 1.0, -1.0)
        axy.scatter(cal[:, 0], cal[:, 1], s=esz, c=np.log10(cal[:, 3] + 1e-6),
                    cmap="plasma", alpha=0.6, lw=0, zorder=2)
        sc = azr.scatter(cal[:, 2], csign * np.hypot(cal[:, 0], cal[:, 1]),
                         s=esz, c=np.log10(cal[:, 3] + 1e-6),
                         cmap="plasma", alpha=0.6, lw=0, zorder=2)
        fig.colorbar(sc, ax=azr, label="log10(calo hit E / GeV)", shrink=0.8)

    if len(trk):
        tsign = np.where(trk[:, 1] >= 0, 1.0, -1.0)
        axy.scatter(trk[:, 0], trk[:, 1], s=1.0, c="#222222", alpha=0.5,
                    lw=0, zorder=3, label=f"tracker hits ({len(trk)})")
        azr.scatter(trk[:, 2], tsign * np.hypot(trk[:, 0], trk[:, 1]),
                    s=1.0, c="#222222", alpha=0.5, lw=0, zorder=3)
        axy.legend(loc="upper right", fontsize=8)

    axy.set_xlabel("x [mm]")
    axy.set_ylabel("y [mm]")
    azr.set_xlabel("z [mm]")
    azr.set_ylabel("R [mm] (sign of y)")
    for ax in (axy, azr):
        ax.set_aspect("equal")

    ecal = cal[:, 3].sum() if len(cal) else 0.0
    fig.suptitle(
        f"{os.path.basename(path)}  event {ievent}: "
        f"{len(trk)} tracker hits, {len(cal)} calo hits "
        f"(sum E = {ecal:.1f} GeV), {len(rays)} MC rays (p > {pmin} GeV)"
    )
    fig.tight_layout()
    fig.savefig(outfile, dpi=160)
    print(f"wrote {outfile}")
    print("collections used:")
    for name, (tname, nn) in sorted(counts.items()):
        print(f"  {name:40s} {tname:30s} n={nn}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", help="*.hepmc (generator) or edm4hep *.root file")
    ap.add_argument("-e", "--event", type=int, default=0, help="event index")
    ap.add_argument("-o", "--output", default=None, help="output PNG")
    ap.add_argument("--pmin", type=float, default=1.0,
                    help="minimum particle momentum to draw [GeV]")
    args = ap.parse_args()

    out = args.output or (
        os.path.splitext(os.path.basename(args.input))[0]
        + f"_ev{args.event}.png"
    )
    if args.input.endswith(".hepmc"):
        display_hepmc(args.input, args.event, out, args.pmin)
    else:
        display_edm4hep(args.input, args.event, out, args.pmin)


if __name__ == "__main__":
    main()
