#!/usr/bin/env python3
"""
make_gridpack.py

Submits Slurm jobs to run Whizard phase-space integration and write VAMP
grid files (.vg) for the WWZ and ZZZ hadronic processes at 10 TeV.
This should be run once before submitting production jobs.

The resulting grid files are saved under GRIDPACK_DIR/<process>/grids/ and can
be loaded by run_chain_WWZ_hadronic.sh / run_chain_ZZZ_hadronic.sh via a symlink
to that directory using:
  ?rebuild_grids = false
  $integrate_workspace = "grids"  (relative — Whizard forbids absolute paths here)
"""

import os
import subprocess
import sys

# --- Configuration ---
WORK_DIR              = "/users/mleblan6/work/bib"
MUCOLL_BENCHMARKS_PATH = os.path.join(WORK_DIR, "mucoll-benchmarks")
GRIDPACK_DIR          = "/oscar/data/mleblan6/mucoll/gridpacks"
APPTAINER_IMAGE       = "/oscar/data/mleblan6/mucoll/mucoll-sim-ubuntu24:main.sif"
DATA_DIR_TO_BIND      = "/oscar/data/mleblan6/mucoll"
LOG_DIR               = os.path.join(GRIDPACK_DIR, "logs")

SPACK_SETUP = (
    "source /opt/spack/opt/spack/__spack_path_placeholder__/__spack_path_placeholder__"
    "/__spack_path_placeholder__/__spack_path_placeholder__"
    "/linux-x86_64/mucoll-stack-2026-01-29-gox6efzvyhus5szcxoq3wscjpt5uxvl7/setup.sh"
)
WHIZARD_LIB = (
    "/opt/spack/opt/spack/__spack_path_placeholder__/__spack_path_placeholder__"
    "/__spack_path_placeholder__/__spack_path_placeholder__"
    "/linux-x86_64/whizard-3.1.5-2wpmahrsf5vaircj7tmf5hdo5fwz2hhw/lib"
)

PROCESSES = {
    "WWZ": {
        "sin_template": os.path.join(
            MUCOLL_BENCHMARKS_PATH,
            "generation/signal/whizard/mumu_WWZ_hadrons_10TeV_gridpack.sin"
        ),
        "workdir":  os.path.join(GRIDPACK_DIR, "grid_mumu_WWZ_hadrons"),
    },
    "ZZZ": {
        "sin_template": os.path.join(
            MUCOLL_BENCHMARKS_PATH,
            "generation/signal/whizard/mumu_ZZZ_hadrons_10TeV_gridpack.sin"
        ),
        "workdir":  os.path.join(GRIDPACK_DIR, "grid_mumu_ZZZ_hadrons"),
    },
}

os.makedirs(LOG_DIR, exist_ok=True)

for name, cfg in PROCESSES.items():
    os.makedirs(cfg["workdir"], exist_ok=True)

    slurm_script = f"""#!/bin/bash
#SBATCH --job-name=whizard_gridpack_{name}
#SBATCH --output={LOG_DIR}/gridpack_{name}.out
#SBATCH --error={LOG_DIR}/gridpack_{name}.err
#SBATCH --time=24:00:00
#SBATCH --mem=32G
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32

echo "========================================"
echo "Whizard gridpack: {name}"
echo "Host: $(hostname)"
echo "========================================"

apptainer exec --bind {DATA_DIR_TO_BIND},{WORK_DIR} {APPTAINER_IMAGE} bash -c '
    set -e
    {SPACK_SETUP}
    export LD_LIBRARY_PATH={WHIZARD_LIB}:$LD_LIBRARY_PATH
    export OMP_NUM_THREADS=32

    WORKDIR={cfg["workdir"]}
    cd $WORKDIR

    # Copy the sin file — it writes .vg files directly to the working directory
    cp {cfg["sin_template"]} ./gridpack.sin

    echo "Running Whizard integration..."
    whizard gridpack.sin

    echo "Grid files written:"
    ls -lh {cfg["workdir"]}/*.vg 2>/dev/null || echo "(no .vg files found, check whizard.log)"
    echo "Gridpack {name} complete."
'
"""

    script_path = f"chains/make_gridpack_{name}.sh"
    with open(script_path, "w") as f:
        f.write(slurm_script)

    try:
        result = subprocess.run(
            ["sbatch", script_path], capture_output=True, text=True, check=True
        )
        print(f"Submitted {name} gridpack job: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"Error submitting {name}: {e.stderr}")
    finally:
        os.remove(script_path)

print(f"\nGrid files will be written to: {GRIDPACK_DIR}/grid_mumu_<PROCESS>_hadrons/grids/")
print("Once complete, pass the gridpack dir to run_chain_*_hadronic.sh as argument 5.")
print("  e.g.:  bash run_chain_WWZ_hadronic.sh 0 100 /output/dir /benchmarks/path /oscar/data/mleblan6/mucoll/gridpacks")
