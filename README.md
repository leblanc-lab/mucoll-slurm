# mucoll-slurm

Run the Muon Collider simulation chain (**GEN → SIM → DIGI → RECO**) on Oscar,
both interactively and as SLURM batch jobs, using the **mucoll-spack v3.1**
container image. Particle-gun studies can be run **with or without BIB**

---

## 1. First-time setup

Check out both repositories side-by-side (they must be siblings). The
benchmarks repo is the **official MuonColliderSoft** one and pulls its
detector configs in as submodules, so clone it with `--recurse-submodules`:

```bash
cd ~/work                     # or wherever you keep code
git clone https://github.com/leblanc-lab/mucoll-slurm.git
git clone --recurse-submodules https://github.com/MuonColliderSoft/mucoll-benchmarks.git
```

Your tree should look like:

```
<your work dir>/
├── mucoll-slurm/        <- this repo
└── mucoll-benchmarks/   <- MuonColliderSoft main, with configs/MAIAConfig etc.
```

The v3.1 image should be pulled once into the shared group data directory:

```
/oscar/data/mleblan6/mucoll/mucoll-sim-ubuntu24:v3.1.sif
```

If you ever need to re-pull it e.g. on another cluster or with an updated image, you can do so with:

```bash
export APPTAINER_TMPDIR=/oscar/scratch/$USER/apptainer_tmp
export APPTAINER_CACHEDIR=/oscar/scratch/$USER/apptainer_cache
mkdir -p $APPTAINER_TMPDIR $APPTAINER_CACHEDIR
apptainer pull mucoll-sim-ubuntu24:v3.1.sif \
    docker://ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:v3.1
```

Finally, open [`config.sh`](config.sh) and skim it. Most values auto-detect; the
first one you may want to change is `OUTPUT_BASE_DIR` (defaults to your own
`$USER` folder inside the shared group area). The image path, benchmarks path,
geometry, and BIB sample locations are already set.

`config.sh` is read by the Python submitters via
`slurm_common.load_config()` and the shell chains `source` it directly, so
there is exactly one place to edit paths. Per-job physics settings (particle, pT,
θ, event/job counts, BIB on/off) and SLURM resources (`TIME`, `MEM`, `CPUS`)
live at the top of each `submit_*.py`.

---

## 2. Run the chain interactively (for debugging)

```bash
source scripts/interact.sh     # grab a worker node (don't run on the login nodes!)
source scripts/shell.sh        # enter the v3.1 container
source scripts/setup.sh        # set up the spack environment
```

Then you can run the same chain a job uses, by hand:

```bash
bash chains/run_chain_pgun.sh --job-id 0 --nevents 1 --outdir /tmp/test \
     --pdg 13 --pt 100 --theta-min 10 --theta-max 170        # add --bib for BIB
```

Or step through the GEN/SIM/DIGI/RECO stages individually — see the per-stage
READMEs in `mucoll-benchmarks/`.

## 3. Submit particle-gun jobs to slurm batch system

Edit the settings at the top of [`submit_pgun.py`](submit_pgun.py) — particle, pT,
theta range, number of jobs/events, and the **`BIB`** switch — then:

```bash
python submit_pgun.py          # run on a login node: it only calls sbatch;
                               # the heavy work runs in the container on the nodes
```

* **Without BIB:** leave `BIB = False`.
* **With BIB:** set `BIB = True`. `run_chain_pgun.sh` then appends to the
  digitization step:

  ```
  --doOverlayFull \
  --OverlayFullPathToMuPlus  $BIB_MUPLUS \
  --OverlayFullPathToMuMinus $BIB_MUMINUS \
  --OverlayFullNumberBackground $BIB_NUMBER
  ```

  The BIB sample directories (`MUPLUS/`, `MUMINUS/` of `.edm4hep.root` files)
  and the overlay count are set in `config.sh`. `BIB_NUMBER` is the number of
  BIB files overlaid per signal event per polarity (default 812; tune per study).

Output layout:

```
$OUTPUT_BASE_DIR/<study>/
├── logs/job_N.{out,err}
└── job_N/{gen,sim,digi,reco}_output_N.edm4hep.root
```

`<study>` auto-names from the particle/pT/θ and BIB state, e.g.
`pgun_pdg13_pt100_theta10-170_nobib`.

### Quick test

Before launching a big batch, sanity-check with one short job: set
`NUM_JOBS = 1`, `NEVENTS_PER_JOB = 1` in `submit_pgun.py` and submit. Confirm the
job finishes and produces a `reco_output_0.edm4hep.root`.

### Parameter scan

To scan over several particles / momenta / angles at once, edit
`PDG_LIST` / `PT_LIST` / `THETA_LIST` (and `BIB`) in
[`submit_pgun_scan.py`](submit_pgun_scan.py), then:

```bash
python submit_pgun_scan.py
```

This creates `$OUTPUT_BASE_DIR/scan[_bib]/pdg{P}_pt{T}_theta{lo}-{hi}/job_N/`.


## 4. Generate benchmark GEN inputs on NERSC

The canonical muon, electron, pion, and photon GEN fixtures can be generated in
one short Slurm job. The submitter pins the smaller v3.1 analysis image (GEN
does not need Geant4/reconstruction) and always defaults to the NERSC `debug`
QoS:

```bash
# One-time image import on a NERSC login node
shifterimg pull ghcr.io/muoncollidersoft/mucoll-analysis-ubuntu24:v3.1

# Inspect the generated batch script without submitting
python submit_benchmark_gen.py --dry-run

# Generate 10,000 events for each particle
python submit_benchmark_gen.py
```

By default the outputs go under
`/global/cfs/cdirs/m5197/mleblanc/MuonCollider/data/benchmark-inputs/v1/`.
Use `--output-dir` to stage them elsewhere. The job also writes `manifest.json`
with checksums, kinematics, seed, benchmark commit, and container provenance.

---

## 5. Whizard signal production (advanced)

[`submit_whizard.py`](submit_whizard.py) drives the Whizard hadronic chains
(steering `.sin` files live in [`whizard/`](whizard/)):

- **WWZ** / **ZZZ** — WW-fusion / ZZ-fusion to hadrons at 10 TeV (Pythia8
  shower/hadronization).
- **Z** — s-channel `mu mu -> Z/gamma* -> qqbar` at full energy (no ISR, so
  m(qqbar) = 10 TeV).
- **Z_RR** — same process with muon-beam ISR: radiative return to the Z pole,
  partonic mass windowed to 60–120 GeV. ISR photons are exactly collinear
  with the beams.

The two s-channel cards use **Pythia6** for shower/hadronization: the
WHIZARD 3.1.5 internal Pythia8 interface breaks energy conservation for
these configurations (c/b strings at 10 TeV; dropped ISR photons for Z_RR)
— see the NOTE comments in the cards before changing this.

1. **(Once)** build the integration grids: `python make_gridpack.py` — writes
   `.vg` grids under `$DATA_GROUP_DIR/gridpacks/`.
2. In `submit_whizard.py`, pick the process(es) in `PROCESSES`, optionally set
   `GRIDPACK_DIR` to the grids from step 1 (leave `""` to integrate in-job),
   then `python submit_whizard.py`.

The v3.1 simulation image includes the event-generator layer, so the Whizard and
particle-gun chains use the same pinned SIF configured in `config.sh`.

### On Perlmutter (NERSC)

`submit_whizard.py` targets Oscar (apptainer, no account/constraint flags) and
will not submit on Perlmutter. Use the NERSC/Shifter driver instead
(`whizard_nersc/submit_whizard_nersc.py`; the cards are shared through this
repo's `whizard/` directory):

```bash
# quick validation in the debug queue (30 min cap; auto-clamped):
python whizard_nersc/submit_whizard_nersc.py --process Z_RR \
    --njobs 1 --nevents 20 --qos debug

# a very fast integration override for pure plumbing checks (NOT physics quality):
python whizard_nersc/submit_whizard_nersc.py --process Z \
    --njobs 1 --nevents 20 --qos debug --iterations '2:1000, 2:2000'

# production:
python whizard_nersc/submit_whizard_nersc.py --process Z_RR --njobs 10 --nevents 1000
```

Both s-channel cards integrate quickly (Z in seconds, Z_RR in a few minutes),
so a 20-event debug-queue test fits the 30-minute cap even with the cards'
full production iterations.

---

## 6. Pythia8 signal production

[`submit_pythia.py`](submit_pythia.py) drives Pythia8 versions of the
s-channel samples. Each process is a `.cmnd` card in [`pythia/`](pythia/), run
through the generic chain [`chains/run_chain_pythia.sh`](chains/run_chain_pythia.sh):

- **Z_pythia** ([`mumu_Z_hadrons_10TeV.cmnd`](pythia/mumu_Z_hadrons_10TeV.cmnd))
  — `mu mu -> Z/gamma* -> qqbar` (q = udscb, full gamma*/Z interference) at
  full energy, `PDF:lepton = off` (no ISR, so m(qqbar) = 10 TeV).
- **Z_RR_pythia** ([`mumu_Z_RR_hadrons_10TeV.cmnd`](pythia/mumu_Z_RR_hadrons_10TeV.cmnd))
  — same process with muon-beam ISR (lepton PDF + QED initial-state shower),
  m̂ windowed to 60–120 GeV.

Unlike the Whizard Z_RR card, where ISR photons are exactly collinear, the
Pythia QED ISR shower gives the photons finite pT; for this colour-singlet
s-channel process it is a power shower, allowed up to the kinematic limit. In ~20% of Z_RR events the hard ISR photon lands in the
detector (θ = 10–170°) and the Z recoils against it.
Both cards leave hadrons with cτ > 10 mm (K0S, Λ, ...) for Geant4 to decay.

The Z_RR card evaluates the lepton PDF at Q² = s (Pythia's default is
Q² = m̂², which undershoots the radiative-return rate by 1.75× at 10 TeV;
see the comment in the card). Cross-checks against the Whizard cards
(2026-10, v3.1 image):

| sample | Pythia8 | Whizard | note |
|--------|---------|---------|------|
| Z      | 7.25 fb | 6.20 fb | α_em(m̂) running in Pythia vs G_μ scheme in Whizard |
| Z_RR   | 19.2 fb | 18.1 fb | LL lepton PDF vs `isr_order = 3` structure function |

The generator is a small C++ driver, [`pythia/pythia_hepmc3.cc`](pythia/pythia_hepmc3.cc)
(`pythia_hepmc3 CARD OUTPUT.hepmc NEVENTS SEED`), compiled at the start of
each job against the image's Pythia 8.315 and HepMC3; it writes HepMC3 that
ddsim reads directly. NEVENTS and the seed (`1234 + JOB_ID`, as in the Whizard
chains) override whatever the card says. There is no gridpack step: Pythia
sets up these 2 → 1 processes in under a second.

```bash
python submit_pythia.py        # edit NUM_JOBS / NEVENTS_PER_JOB / PROCESSES first
```

To run a different process, drop a new card in `pythia/` and add a
`(label, card)` entry to `PROCESSES`. Interactively, inside the container:

```bash
bash chains/run_chain_pythia.sh 0 1 /tmp/test ../mucoll-benchmarks mumu_Z_RR_hadrons_10TeV.cmnd
```

---
