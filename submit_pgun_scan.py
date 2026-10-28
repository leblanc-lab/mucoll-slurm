#!/usr/bin/env python3
"""Submit a grid scan of particle-gun jobs over PDG x pT x theta.

Like submit_pgun.py, but loops over lists of parameters. Edit the lists below,
then:

    python submit_pgun_scan.py

All paths come from config.sh. Output is organised as:
    $OUTPUT_BASE_DIR/scan[_bib]/pdg{P}_pt{T}_theta{lo}-{hi}/job_N/
"""

import itertools
import os

import slurm_common as sc

# =============================== EDIT ME ====================================
NUM_JOBS_PER_POINT = 2
FIRST_JOB_ID = 0         # raise to add more jobs to an existing scan
NEVENTS_PER_JOB = 1000

PDG_LIST = [11, 13, 211]                            # e, mu, pi
PT_LIST = [10, 50, 100]                             # GeV
THETA_LIST = [(10, 170), (30, 150), (80, 100)]      # (min, max) deg

BIB = False              # <-- flip to True to overlay BIB on every point

SCAN_NAME = ""           # optional label for the top output folder; "" = auto

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
    scan_root = os.path.join(
        cfg["OUTPUT_BASE_DIR"], SCAN_NAME or f"scan_{bib_tag}"
    )

    points = list(itertools.product(PDG_LIST, PT_LIST, THETA_LIST))
    total = len(points) * NUM_JOBS_PER_POINT
    print(f"Scan: {len(points)} points x {NUM_JOBS_PER_POINT} jobs = {total} jobs "
          f"[BIB={'on' if BIB else 'off'}]")
    print(f"  output -> {scan_root}")

    n_ok = 0
    for pdg, pt, (theta_min, theta_max) in points:
        point = f"pdg{pdg}_pt{pt}_theta{theta_min}-{theta_max}"
        out_dir = os.path.join(scan_root, point)
        log_dir = os.path.join(out_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        print(f"- {point}")

        for i in range(FIRST_JOB_ID, FIRST_JOB_ID + NUM_JOBS_PER_POINT):
            chain_args = [
                "--job-id", i,
                "--nevents", NEVENTS_PER_JOB,
                "--outdir", out_dir,
                "--pdg", pdg,
                "--pt", pt,
                "--theta-min", theta_min,
                "--theta-max", theta_max,
                "--seed", sc.pgun_seed(pdg, pt, theta_min, theta_max, i),
            ]
            if BIB:
                chain_args.append("--bib")

            body = (
                'echo "Host: $(hostname)"\n'
                f'echo "scan {point} job {i} (BIB={BIB})"\n\n'
                + sc.apptainer_cmd(cfg, chain, chain_args)
            )
            slurm_script = sc.make_slurm_script(
                job_name=f"scan_{point}_{i}",
                out_log=os.path.join(log_dir, f"job_{i}.out"),
                err_log=os.path.join(log_dir, f"job_{i}.err"),
                sbatch_directives=[
                    f"--time={TIME}", f"--mem={MEM}",
                    "--nodes=1", "--ntasks=1", f"--cpus-per-task={CPUS}",
                ],
                body=body,
            )
            print(f"  job {i}:", end="")
            if sc.submit(slurm_script, f"_submit_pgun_scan_{point}_{i}.sh"):
                n_ok += 1

    print(f"\nSubmitted {n_ok}/{total} jobs.")


if __name__ == "__main__":
    main()
