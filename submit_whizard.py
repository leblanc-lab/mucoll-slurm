#!/usr/bin/env python3
"""Submit Whizard *signal* production jobs (WWZ / ZZZ hadronic) to SLURM.

For particle-gun studies use submit_pgun.py instead -- this script drives the
Whizard chains, which take a different (positional) argument convention and an
optional pre-computed gridpack directory.

Edit the knobs below, then:  python submit_whizard.py
All paths come from config.sh.
"""

import os

import slurm_common as sc

# =============================== EDIT ME ====================================
NUM_JOBS = 10
NEVENTS_PER_JOB = 100

# Which signal processes to run. Comment a line out to skip it.
PROCESSES = [
    ("WWZ", "chains/run_chain_WWZ_hadronic.sh"),
    # ("ZZZ", "chains/run_chain_ZZZ_hadronic.sh"),
]

# Pre-computed Whizard VAMP grids (from make_gridpack.py). Leave "" to run the
# full phase-space integration inside each job (much slower).
GRIDPACK_DIR = ""        # e.g. f"{DATA_GROUP_DIR}/gridpacks"

# SLURM resources
TIME = "08:00:00"
MEM = "16G"
CPUS = 4
# ============================================================================


def main():
    cfg = sc.load_config()
    sc.validate_paths(cfg)
    if not os.path.exists(cfg["WHIZARD_IMAGE"]):
        raise SystemExit(
            f"Error: WHIZARD_IMAGE not found at {cfg['WHIZARD_IMAGE']}.\n"
            "Set WHIZARD_IMAGE in config.sh to a v3.1 (or newer) sim image "
            "that includes the generator layer."
        )

    gridpack = GRIDPACK_DIR  # "" disables gridpacks (full integration each job)

    print(f"Submitting {NUM_JOBS} job(s) x {len(PROCESSES)} process(es).")
    print(f"  output -> {cfg['OUTPUT_BASE_DIR']}")
    if gridpack:
        print(f"  gridpack -> {gridpack}")

    n_ok = 0
    for label, rel_script in PROCESSES:
        chain = os.path.join(cfg["WORK_DIR"], "mucoll-slurm", rel_script)
        if not os.path.exists(chain):
            raise SystemExit(f"Error: chain script not found: {chain}")
        os.chmod(chain, 0o755)

        out_dir = os.path.join(cfg["OUTPUT_BASE_DIR"], label)
        log_dir = os.path.join(out_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        print(f"\n--- {label} ---")

        for job_id in range(NUM_JOBS):
            # Whizard chains: JOB_ID NEVENTS OUTPUT_DIR BENCHMARKS [GRIDPACK_DIR]
            chain_args = [job_id, NEVENTS_PER_JOB, out_dir,
                          cfg["MUCOLL_BENCHMARKS_PATH"]]
            if gridpack:
                chain_args.append(gridpack)

            body = (
                'echo "Host: $(hostname)"\n'
                f'echo "{label} job {job_id}"\n\n'
                + sc.apptainer_cmd(cfg, chain, chain_args,
                                   image=cfg["WHIZARD_IMAGE"])
            )
            slurm_script = sc.make_slurm_script(
                job_name=f"{label}_{job_id}",
                out_log=os.path.join(log_dir, f"job_{job_id}.out"),
                err_log=os.path.join(log_dir, f"job_{job_id}.err"),
                sbatch_directives=[
                    f"--time={TIME}", f"--mem={MEM}",
                    "--nodes=1", "--ntasks=1", f"--cpus-per-task={CPUS}",
                ],
                body=body,
            )
            print(f"job {job_id}:", end="")
            if sc.submit(slurm_script, f"_submit_{label}_{job_id}.sh"):
                n_ok += 1

    print(f"\nSubmitted {n_ok}/{NUM_JOBS * len(PROCESSES)} jobs.")


if __name__ == "__main__":
    main()
