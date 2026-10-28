#!/usr/bin/env python3
"""Submit particle-gun (pgun) jobs to SLURM -- with or without BIB.

This is the everyday driver for the interns. Edit the few knobs below, then:

    python submit_pgun.py

All paths (image, benchmarks, output, BIB samples) come from config.sh.
For a parameter scan over several PDGs / pTs / angles, use submit_pgun_scan.py.
"""

import os

import slurm_common as sc

# =============================== EDIT ME ====================================
NUM_JOBS = 10            # how many jobs to submit
FIRST_JOB_ID = 0         # raise to add more jobs to an existing study
NEVENTS_PER_JOB = 100    # events per job

PDG = 13                 # particle: 11=e, 13=mu, 22=gamma, 211=pi+, 2112=n ...
PT = 100                 # transverse momentum [GeV]
THETA_MIN = 10           # min polar angle [deg]
THETA_MAX = 170          # max polar angle [deg]

BIB = False              # <-- flip to True to overlay Beam-Induced Background

STUDY_NAME = ""          # optional label for the output subfolder; "" = auto

# SLURM resources
TIME = "08:00:00"
MEM = "16G"
CPUS = 4
# ============================================================================


def main():
    cfg = sc.load_config()
    sc.validate_paths(cfg)

    chain = os.path.join(cfg["WORK_DIR"], "mucoll-slurm/chains/run_chain_pgun.sh")
    os.chmod(chain, 0o755)

    bib_tag = "bib" if BIB else "nobib"
    study = STUDY_NAME or f"pgun_pdg{PDG}_pt{PT}_theta{THETA_MIN}-{THETA_MAX}_{bib_tag}"
    out_dir = os.path.join(cfg["OUTPUT_BASE_DIR"], study)
    log_dir = os.path.join(out_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    print(f"Submitting {NUM_JOBS} pgun job(s)  [BIB={'on' if BIB else 'off'}]")
    print(f"  particle PDG={PDG}, pT={PT} GeV, theta=[{THETA_MIN}, {THETA_MAX}]")
    print(f"  output -> {out_dir}")

    n_ok = 0
    for job_id in range(FIRST_JOB_ID, FIRST_JOB_ID + NUM_JOBS):
        chain_args = [
            "--job-id", job_id,
            "--nevents", NEVENTS_PER_JOB,
            "--outdir", out_dir,
            "--pdg", PDG,
            "--pt", PT,
            "--theta-min", THETA_MIN,
            "--theta-max", THETA_MAX,
            "--seed", sc.pgun_seed(PDG, PT, THETA_MIN, THETA_MAX, job_id),
        ]
        if BIB:
            chain_args.append("--bib")

        body = (
            'echo "Host: $(hostname)"\n'
            f'echo "pgun job {job_id} (BIB={BIB})"\n\n'
            + sc.apptainer_cmd(cfg, chain, chain_args)
        )
        slurm_script = sc.make_slurm_script(
            job_name=f"pgun_{bib_tag}_{job_id}",
            out_log=os.path.join(log_dir, f"job_{job_id}.out"),
            err_log=os.path.join(log_dir, f"job_{job_id}.err"),
            sbatch_directives=[
                f"--time={TIME}", f"--mem={MEM}",
                "--nodes=1", "--ntasks=1", f"--cpus-per-task={CPUS}",
            ],
            body=body,
        )
        print(f"job {job_id}:", end="")
        if sc.submit(slurm_script, f"_submit_pgun_{job_id}.sh"):
            n_ok += 1

    print(f"\nSubmitted {n_ok}/{NUM_JOBS} jobs.")


if __name__ == "__main__":
    main()
