# BIB production (v3.0, Perlmutter)

FLUKA → GEN → SIM → DIGI → RECO run as **four separate sets of batch jobs**,
each driven by PyTaskFarmer (N workers/node consuming a shared task list) via
Shifter with the `mucoll-sim-ubuntu24:v3.0` image. Ported from the old
`~/bib/mucoll-slurm/bib` toolkit and adapted to the new benchmarks steering
(`setup_config.sh`, `--inputFiles/--outputFile`, `--numThreads`).

**These scripts are intended to be run on Perlmutter (NERSC), using PyTaskFarmer to manage the batch jobs!**

https://gitlab.cern.ch/berkeleylab/pytaskfarmer

## Files
- `config.sh` — the one file to edit: paths, image, geometry, per-step
  nodes/workers/threads/wall-time.
- `run_{gen,sim,digi,reco}.sh` — per-step worker scripts (run inside the container).
- `submit_bib.py` — builds each step's task list + SLURM script and `sbatch`es it.
- `test_chain_single.sh` — one-file GEN→SIM→DIGI→RECO smoke test (run first!).
- `benchmark_production.py` — per-step timing/throughput/RSS summary from the
  PyTaskFarmer timelines and GNU `time -v` logs.

## Workflow
```bash
cd mucoll-slurm/bib

# 0. One-time: pull the image   shifterimg pull ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:v3.0

# 1. Smoke-test the whole chain on a login node (uses the real run_*.sh)
bash test_chain_single.sh

# 2. Small test batch (debug QoS, 4 files → 8 tasks/step)
python submit_bib.py --step all --nfiles 4

# 3. Full production (chained: sim afterok gen, etc.)
python submit_bib.py --step all

# Resubmit to retry unfinished tasks (PTF skips completed ones)
python submit_bib.py --step reco

# 4. Benchmark once jobs have run
python benchmark_production.py            # all steps
python benchmark_production.py --csv bench.csv
```

## Notes
- Both beam directions are produced: `MUPLUS` (normal) and `MUMINUS` (`-z`),
  under `OUTPUT_BASE/<STEP>/<BEAM>/`.
- RECO uses fewer workers × more ACTS/Gaudi threads (`RECO_WORKERS=32`,
  `RECO_THREADS=4`) to cut memory pressure; tune in `config.sh`.
- Each task writes `<output>.time.log` (GNU `time -v`) and PyTaskFarmer records
  `logs/<step>/ptf_workdir/timeline.json` — both consumed by the benchmarker.
