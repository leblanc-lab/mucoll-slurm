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

import slurm_common as sc

# --- Configuration (paths come from config.sh) ---
_cfg                   = sc.load_config()
WORK_DIR               = _cfg["WORK_DIR"]
MUCOLL_BENCHMARKS_PATH = _cfg["MUCOLL_BENCHMARKS_PATH"]
GRIDPACK_DIR           = os.path.join(_cfg["DATA_GROUP_DIR"], "gridpacks")
# Keep the image selectable independently even though v3.1 includes Whizard.
APPTAINER_IMAGE        = _cfg["WHIZARD_IMAGE"]
DATA_DIR_TO_BIND       = _cfg["DATA_BIND"]
LOG_DIR                = os.path.join(GRIDPACK_DIR, "logs")

# Prefer the image's official setup script; fall back to a glob for old images.
SPACK_SETUP = (
    'if [ -f /opt/setup_mucoll.sh ]; then source /opt/setup_mucoll.sh; '
    'else source $(ls /opt/spack/opt/spack/*/*/*/*/linux-x86_64/'
    'mucoll-stack-*/setup.sh 2>/dev/null | sort | tail -n1); fi'
)
WHIZARD_LIB = (
    '$(ls -d /opt/spack/opt/spack/*/*/*/*/linux-x86_64/'
    'whizard-*/lib 2>/dev/null | sort | tail -n1)'
)

# Whizard .sin templates are kept in this repo (mucoll-slurm/whizard/).
WHIZARD_SIN_DIR = os.path.join(WORK_DIR, "mucoll-slurm", "whizard")

PROCESSES = {
    "WWZ": {
        "sin_template": os.path.join(
            WHIZARD_SIN_DIR, "mumu_WWZ_hadrons_10TeV_gridpack.sin"
        ),
        "workdir":  os.path.join(GRIDPACK_DIR, "grid_mumu_WWZ_hadrons"),
    },
    "ZZZ": {
        "sin_template": os.path.join(
            WHIZARD_SIN_DIR, "mumu_ZZZ_hadrons_10TeV_gridpack.sin"
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
