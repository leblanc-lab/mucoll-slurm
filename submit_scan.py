import os
import subprocess
import sys
import itertools

# --- Configuration ---
NUM_JOBS_PER_POINT = 2      # Number of jobs to submit per scan point
NEVENTS_PER_JOB = 1000       # Events per job
OUTPUT_BASE_DIR = "/oscar/data/mleblan6/mucoll/batch_output/scan"
WORK_DIR = "/users/mleblan6/work/mucoll"
MUCOLL_BENCHMARKS_PATH = os.path.join(WORK_DIR, "mucoll-benchmarks")
SCRIPT_PATH = os.path.join(WORK_DIR, "mucoll-slurm/run_chain.sh")
APPTAINER_IMAGE = "docker://ghcr.io/muoncollidersoft/mucoll-sim-alma9:full_gaudi_test"
DATA_DIR_TO_BIND = "/oscar/data/mleblan6/mucoll"

# --- Scan Parameters ---
# Define the lists of parameters to scan over
PDG_LIST = [11, 13, 211]        # e.g., Electron, Muon, Pion
PT_LIST = [10, 50, 100]         # GeV
THETA_LIST = [(10, 170), (30, 150), (80, 100)] # (Min, Max) degrees

# --- Validation ---
if not os.path.exists(MUCOLL_BENCHMARKS_PATH):
    print(f"Error: Benchmarks path not found: {MUCOLL_BENCHMARKS_PATH}")
    sys.exit(1)

if not os.path.exists(SCRIPT_PATH):
    print(f"Error: Script not found: {SCRIPT_PATH}")
    sys.exit(1)

# Ensure script is executable
os.chmod(SCRIPT_PATH, 0o755)

# Create base output directory
os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)

print(f"Starting scan submission...")
print(f"Jobs per point: {NUM_JOBS_PER_POINT}")
print(f"Events per job: {NEVENTS_PER_JOB}")
print(f"Output base: {OUTPUT_BASE_DIR}")

# Generate all combinations
combinations = list(itertools.product(PDG_LIST, PT_LIST, THETA_LIST))
total_jobs = len(combinations) * NUM_JOBS_PER_POINT

print(f"Total configurations: {len(combinations)}")
print(f"Total jobs to submit: {total_jobs}")

job_counter = 0

for pdg, pt, (theta_min, theta_max) in combinations:
    # Create a specific output directory for this configuration
    # Naming convention: pdg_{pdg}_pt_{pt}_theta_{min}-{max}
    config_name = f"pdg_{pdg}_pt_{pt}_theta_{theta_min}-{theta_max}"
    config_dir = os.path.join(OUTPUT_BASE_DIR, config_name)
    log_dir = os.path.join(config_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    print(f"Submitting for {config_name}...")

    for i in range(NUM_JOBS_PER_POINT):
        job_id = job_counter
        job_name = f"mc_{config_name}_{i}"
        
        # Slurm script content
        slurm_script = f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output={log_dir}/job_{i}.out
#SBATCH --error={log_dir}/job_{i}.err
#SBATCH --time=04:00:00
#SBATCH --mem=4G
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1

echo "Running on host: $(hostname)"
echo "Job Index: {i}"
echo "Configuration: PDG={pdg}, pT={pt}, Theta=[{theta_min}, {theta_max}]"

# Run the container
# We bind the data directory explicitly, and the work directory
apptainer exec --bind {DATA_DIR_TO_BIND},{WORK_DIR} {APPTAINER_IMAGE} bash {SCRIPT_PATH} {i} {NEVENTS_PER_JOB} {config_dir} {MUCOLL_BENCHMARKS_PATH} {pdg} {pt} {theta_min} {theta_max}
"""
        
        script_filename = f"submit_{config_name}_{i}.sh"
        with open(script_filename, "w") as f:
            f.write(slurm_script)
            
        # Submit the job
        try:
            result = subprocess.run(["sbatch", script_filename], capture_output=True, text=True, check=True)
            print(f"  Submitted job {i} (Global ID {job_id}): {result.stdout.strip()}")
            job_counter += 1
        except subprocess.CalledProcessError as e:
            print(f"  Error submitting job {i}: {e.stderr}")
        finally:
            if os.path.exists(script_filename):
                os.remove(script_filename)

print("All submissions complete.")
