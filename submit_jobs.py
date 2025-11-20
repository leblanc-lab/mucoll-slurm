import os
import subprocess
import sys

# --- Configuration ---
NUM_JOBS = 5                # Number of jobs to submit
NEVENTS_PER_JOB = 1000      # Events per job
OUTPUT_BASE_DIR = "/oscar/data/mleblan6/mucoll/batch_output"
WORK_DIR = "/users/mleblan6/work/mucoll"
MUCOLL_BENCHMARKS_PATH = os.path.join(WORK_DIR, "mucoll-benchmarks")
SCRIPT_PATH = os.path.join(WORK_DIR, "mucoll-slurm/run_chain.sh")
APPTAINER_IMAGE = "docker://ghcr.io/muoncollidersoft/mucoll-sim-alma9:full_gaudi_test"
DATA_DIR_TO_BIND = "/oscar/data/mleblan6/mucoll"

# --- Validation ---
if not os.path.exists(MUCOLL_BENCHMARKS_PATH):
    print(f"Error: Benchmarks path not found: {MUCOLL_BENCHMARKS_PATH}")
    sys.exit(1)

if not os.path.exists(SCRIPT_PATH):
    print(f"Error: Script not found: {SCRIPT_PATH}")
    sys.exit(1)

# Ensure script is executable
os.chmod(SCRIPT_PATH, 0o755)

# Create output directory
os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)

print(f"Submitting {NUM_JOBS} jobs with {NEVENTS_PER_JOB} events each.")
print(f"Output will be in {OUTPUT_BASE_DIR}")

for job_id in range(NUM_JOBS):
    job_name = f"mucoll_job_{job_id}"
    log_dir = os.path.join(OUTPUT_BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Slurm script content
    # We bind the data directory so it's accessible inside the container
    slurm_script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output={log_dir}/job_{job_id}.out
#SBATCH --error={log_dir}/job_{job_id}.err
#SBATCH --time=04:00:00
#SBATCH --mem=4G
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1

echo "Running on host: $(hostname)"
echo "Job ID: {job_id}"

# Run the container
# We bind the data directory explicitly, and the work directory to ensure all scripts are found
apptainer exec --bind {DATA_DIR_TO_BIND},{WORK_DIR} {APPTAINER_IMAGE} bash {SCRIPT_PATH} {job_id} {NEVENTS_PER_JOB} {OUTPUT_BASE_DIR} {MUCOLL_BENCHMARKS_PATH}
"""
    
    script_filename = f"submit_job_{job_id}.sh"
    with open(script_filename, "w") as f:
        f.write(slurm_script)
        
    # Submit the job
    try:
        result = subprocess.run(["sbatch", script_filename], capture_output=True, text=True, check=True)
        print(f"Submitted job {job_id}: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"Error submitting job {job_id}: {e.stderr}")
    finally:
        if os.path.exists(script_filename):
            os.remove(script_filename)

print("Submission complete.")
