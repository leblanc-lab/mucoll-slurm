#!/usr/bin/env python3
"""Submit Pythia8 *signal* production jobs (s-channel Z / Z_RR hadronic) to SLURM.

Pythia8 counterparts of the Whizard s-channel samples in submit_whizard.py.
Each process is a .cmnd card in pythia/, run through the generic
chains/run_chain_pythia.sh (GEN -> SIM -> DIGI -> RECO). No gridpack step:
Pythia integrates these 2 -> 1 processes on the fly in well under a second.

Edit the knobs below, then:  python submit_pythia.py
All paths come from config.sh.
"""

import os

import slurm_common as sc

# =============================== EDIT ME ====================================
NUM_JOBS = 10
NEVENTS_PER_JOB = 100

# Which processes to run: (label, card in pythia/). Comment a line out to skip.
PROCESSES = [
    # s-channel Z/gamma* -> qqbar at full energy (no ISR)
    ("Z_pythia", "mumu_Z_hadrons_10TeV.cmnd"),
    # ISR radiative return to the Z pole (60-120 GeV window)
    ("Z_RR_pythia", "mumu_Z_RR_hadrons_10TeV.cmnd"),
]

CHAIN = "chains/run_chain_pythia.sh"

# SLURM resources
TIME = "08:00:00"
MEM = "16G"
CPUS = 4
# ============================================================================


def main():
    cfg = sc.load_config()
    sc.validate_paths(cfg)

    chain = os.path.join(cfg["WORK_DIR"], "mucoll-slurm", CHAIN)
    if not os.path.exists(chain):
        raise SystemExit(f"Error: chain script not found: {chain}")
    os.chmod(chain, 0o755)

    print(f"Submitting {NUM_JOBS} job(s) x {len(PROCESSES)} process(es).")
    print(f"  output -> {cfg['OUTPUT_BASE_DIR']}")

    n_ok = 0
    for label, card in PROCESSES:
        card_path = os.path.join(cfg["WORK_DIR"], "mucoll-slurm", "pythia", card)
        if not os.path.exists(card_path):
            raise SystemExit(f"Error: Pythia8 card not found: {card_path}")

        out_dir = os.path.join(cfg["OUTPUT_BASE_DIR"], label)
        log_dir = os.path.join(out_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        print(f"\n--- {label} ({card}) ---")

        for job_id in range(NUM_JOBS):
            # Pythia chain: JOB_ID NEVENTS OUTPUT_DIR BENCHMARKS CARD [LABEL]
            chain_args = [job_id, NEVENTS_PER_JOB, out_dir,
                          cfg["MUCOLL_BENCHMARKS_PATH"], card, label]

            body = (
                'echo "Host: $(hostname)"\n'
                f'echo "{label} job {job_id}"\n\n'
                + sc.apptainer_cmd(cfg, chain, chain_args)
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
