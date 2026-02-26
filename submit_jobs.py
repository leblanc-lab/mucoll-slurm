import os
import subprocess
import sys

# --- Configuration ---
NUM_JOBS = 10                # Number of jobs per process
NEVENTS_PER_JOB = 100        # Events per job
OUTPUT_BASE_DIR = "/oscar/data/mleblan6/mucoll/mleblan6"
WORK_DIR = "/users/mleblan6/work/bib"
MUCOLL_BENCHMARKS_PATH = os.path.join(WORK_DIR, "mucoll-benchmarks")
# Set to the directory containing pre-computed Whizard VAMP grids, or leave
# empty ("") to run the full phase-space integration inside each job.
GRIDPACK_DIR = "/oscar/data/mleblan6/mucoll/gridpacks"  # set "" to disable

# I have already pulled the image and converted it to a SIF:
# apptainer pull --name mucoll-sim-ubuntu24:main.sif docker://ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:main
APPTAINER_IMAGE = "/oscar/data/mleblan6/mucoll/mucoll-sim-ubuntu24:main.sif"
DATA_DIR_TO_BIND = "/oscar/data/mleblan6/mucoll"

# --- Processes to submit ---
# Add or comment out entries to control which processes are submitted.
# Each entry: (label, run_chain_script)
PROCESSES = [
    # ("MuMu_WWZ_Hadronic", os.path.join(WORK_DIR, "mucoll-slurm/chains/run_chain_WWZ_hadronic.sh")),
    # ("MuMu_ZZZ_Hadronic", os.path.join(WORK_DIR, "mucoll-slurm/chains/run_chain_ZZZ_hadronic.sh")),
    ("pgun", os.path.join(WORK_DIR, "mucoll-slurm/chains/run_chain_pgun.sh")),
]

# --- Validation ---
if not os.path.exists(MUCOLL_BENCHMARKS_PATH):
    print(f"Error: Benchmarks path not found: {MUCOLL_BENCHMARKS_PATH}")
    sys.exit(1)

for label, script_path in PROCESSES:
    if not os.path.exists(script_path):
        print(f"Error: Script not found for {label}: {script_path}")
        sys.exit(1)
    os.chmod(script_path, 0o755)

os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
print(f"Submitting {NUM_JOBS} jobs x {len(PROCESSES)} process(es) = {NUM_JOBS * len(PROCESSES)} total jobs.")
print(f"Output will be in {OUTPUT_BASE_DIR}")

# Launch jobs for each process specified above.
for label, script_path in PROCESSES:
    print(f"\n--- Process: {label} ---")
    for job_id in range(NUM_JOBS):
        job_name = f"mucoll_{label}_{job_id}"
        log_dir = os.path.join(OUTPUT_BASE_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)

        slurm_script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output={log_dir}/{label}_job_{job_id}.out
#SBATCH --error={log_dir}/{label}_job_{job_id}.err
#SBATCH --time=08:00:00
#SBATCH --mem=16G
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4

echo "Running on host: $(hostname)"
echo "Process: {label}  Job ID: {job_id}"

# Run the container
# We bind the data directory explicitly, and the work directory to ensure all scripts are found
apptainer exec --bind {DATA_DIR_TO_BIND},{WORK_DIR} {APPTAINER_IMAGE} bash {script_path} {job_id} {NEVENTS_PER_JOB} {OUTPUT_BASE_DIR} {MUCOLL_BENCHMARKS_PATH} {GRIDPACK_DIR}
"""

        script_filename = f"submit_{label}_{job_id}.sh"
        with open(script_filename, "w") as f:
            f.write(slurm_script)

        try:
            result = subprocess.run(["sbatch", script_filename], capture_output=True, text=True, check=True)
            print(f"  Submitted {label} job {job_id}: {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            print(f"  Error submitting {label} job {job_id}: {e.stderr}")
        finally:
            if os.path.exists(script_filename):
                os.remove(script_filename)

print("Submission complete.")
