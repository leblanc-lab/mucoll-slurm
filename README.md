# Batch Processing for MuColl Benchmarks

This directory contains scripts to run the full Muon Collider simulation chain (Generation -> Simulation -> Digitization -> Reconstruction) on a Slurm batch system using Apptainer.

## Scripts

- **`submit_jobs.py`**: The main Python script that generates Slurm submission scripts and submits them using `sbatch`.
- **`run_chain.sh`**: The shell script that is executed by each job inside the Apptainer container. It orchestrates the 4 steps of the simulation chain.

## Prerequisites

- Access to a Slurm cluster (like OSCAR).
- Apptainer installed and available.
- The MuColl Apptainer image (e.g., `docker://ghcr.io/muoncollidersoft/mucoll-sim-alma9:full_gaudi_test`).

## Usage

1.  **Configure the submission**:
    Open `submit_jobs.py` and edit the configuration section at the top:

    ```python
    # --- Configuration ---
    NUM_JOBS = 5                # Number of jobs to submit
    NEVENTS_PER_JOB = 1000      # Events per job
    OUTPUT_BASE_DIR = "/oscar/data/mleblan6/mucoll/batch_output" # Where output files will go
    # ... other paths ...
    ```

    Ensure `OUTPUT_BASE_DIR` points to a location where you have write permissions and plenty of space.

2.  **Submit the jobs**:
    Run the submission script from the terminal (outside the container, on the login node):

    ```bash
    python submit_jobs.py
    ```

    This will:
    - Create the output directory if it doesn't exist.
    - Loop `NUM_JOBS` times.
    - For each job, create a temporary Slurm script (`submit_job_X.sh`).
    - Submit the script via `sbatch`.
    - Clean up the temporary script.

## Output Structure

The output directory will be organized as follows:

```
/path/to/output/
├── logs/
│   ├── job_0.out
│   ├── job_0.err
│   └── ...
├── job_0/
│   ├── gen_output_0.edm4hep.root
│   ├── sim_output_0.edm4hep.root
│   ├── digi_output_0.edm4hep.root
│   └── reco_output_0.edm4hep.root
├── job_1/
│   └── ...
└── ...
```

## Customization

- **Simulation Chain**: To modify the physics or steps run, edit `run_chain.sh`.
- **Resources**: To change memory or time limits, edit the `#SBATCH` directives inside the `slurm_script` string in `submit_jobs.py`.
