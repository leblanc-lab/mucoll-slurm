#!/usr/bin/env python3
"""submit_bib.py - Submit BIB GEN/SIM/DIGI/RECO via PyTaskFarmer on Perlmutter.

Each step is submitted as its own set of full-node SLURM jobs. Every node runs
PyTaskFarmer, which forks N worker processes that consume tasks from a shared
file-locked task list. If a node runs out of wall time, just resubmit the same
command -- PyTaskFarmer skips tasks that already finished.

The four steps form a dependency chain (sim afterok gen, etc.) when submitted
together, but each is a *dedicated* batch submission so the whole production can
be benchmarked step by step.

Usage:
    python submit_bib.py --step gen [--nfiles N] [--dry-run]
    python submit_bib.py --step sim --depend JOBID
    python submit_bib.py --step all
"""

import argparse
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_config(path):
    cfg = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            val = val.partition("#")[0]                       # strip inline comment
            val = val.strip().strip('"').strip("'")
            # expand ${VAR:-default} using the real env or the embedded default
            val = re.sub(r'\$\{(\w+):-([^}]*)\}',
                         lambda m: os.environ.get(m.group(1), m.group(2)), val)
            cfg[key.strip()] = val
    return cfg


CFG = parse_config(os.path.join(SCRIPT_DIR, "config.sh"))

FLUKA_INPUT_DIR   = CFG["FLUKA_INPUT_DIR"]
OUTPUT_BASE       = CFG["OUTPUT_BASE"]
MUCOLL_BENCHMARKS = CFG["MUCOLL_BENCHMARKS"]
IMAGE             = CFG["CONTAINER_IMAGE"]
ACCOUNT           = CFG["SLURM_ACCOUNT"]
CONSTRAINT        = CFG["SLURM_CONSTRAINT"]
QOS_PROD          = CFG["SLURM_QOS_PROD"]
QOS_TEST          = CFG["SLURM_QOS_TEST"]
DETECTOR_GEOM     = CFG["DETECTOR_GEOM"]
PYTASKFARMER      = CFG["PYTASKFARMER"]

# Per-step: (wall-time, nodes, workers/node, threads/worker)
STEP_RES = {
    "gen":  (CFG["GEN_TIME"],  int(CFG["GEN_NODES"]),  int(CFG["GEN_WORKERS"]),  1),
    "sim":  (CFG["SIM_TIME"],  int(CFG["SIM_NODES"]),  int(CFG["SIM_WORKERS"]),  1),
    "digi": (CFG["DIGI_TIME"], int(CFG["DIGI_NODES"]), int(CFG["DIGI_WORKERS"]), int(CFG["DIGI_THREADS"])),
    "reco": (CFG["RECO_TIME"], int(CFG["RECO_NODES"]), int(CFG["RECO_WORKERS"]), int(CFG["RECO_THREADS"])),
}

GEN_BX_TIME       = CFG["GEN_BX_TIME"]
GEN_NORMALIZATION = CFG["GEN_NORMALIZATION"]
GEN_T_MAX         = CFG.get("GEN_T_MAX", "")
GEN_NE_MIN        = CFG.get("GEN_NE_MIN", "")
GEN_PDGS          = CFG.get("GEN_PDGS", "")
GEN_NOPDGS        = CFG.get("GEN_NOPDGS", "")

STEP_ORDER = ["gen", "sim", "digi", "reco"]
BEAMS = ["MUPLUS", "MUMINUS"]


def discover_inputs():
    files = sorted(
        os.path.join(FLUKA_INPUT_DIR, f)
        for f in os.listdir(FLUKA_INPUT_DIR)
        if f.startswith("summary") and f.endswith("_DET_IP.dat")
    )
    if not files:
        sys.exit(f"ERROR: no summary*_DET_IP.dat files in {FLUKA_INPUT_DIR}")
    return files


def task_command(step, beam, idx, input_file):
    """Return the single shell command PyTaskFarmer runs for one task."""
    worker  = os.path.join(SCRIPT_DIR, f"run_{step}.sh")
    _, _, _, threads = STEP_RES[step]

    if step == "gen":
        out_dir = os.path.join(OUTPUT_BASE, "GEN", beam)
        output  = f"{out_dir}/bib_gen_{idx}.edm4hep.root"
        # Build optional flags in Python to avoid empty positional placeholders
        # that would break PTF's command.split() execution.
        extra = []
        if beam == "MUMINUS":
            extra.append("-z")
        if GEN_T_MAX:
            extra += ["--t_max", GEN_T_MAX]
        if GEN_NE_MIN:
            extra += ["--ne_min", GEN_NE_MIN]
        if GEN_PDGS:
            extra += ["--pdgs"] + GEN_PDGS.split()
        if GEN_NOPDGS:
            extra += ["--nopdgs"] + GEN_NOPDGS.split()
        args = f'{input_file} {output} {MUCOLL_BENCHMARKS} {GEN_BX_TIME} {GEN_NORMALIZATION}'
        if extra:
            args += ' ' + ' '.join(extra)
    else:
        prev_step = {"sim": "gen", "digi": "sim", "reco": "digi"}[step]
        prev_dir  = {"sim": "GEN", "digi": "SIM", "reco": "DIGI"}[step]
        input_file = f"{OUTPUT_BASE}/{prev_dir}/{beam}/bib_{prev_step}_{idx}.edm4hep.root"
        out_dir    = os.path.join(OUTPUT_BASE, step.upper(), beam)
        output     = f"{out_dir}/bib_{step}_{idx}.edm4hep.root"
        args       = f'{input_file} {output} {MUCOLL_BENCHMARKS} {DETECTOR_GEOM}'
        if step in ("digi", "reco"):
            args += f' {threads}'

    return f'shifter --image={IMAGE} bash {worker} {args}'


def write_tasklist(step, files):
    """Write one command per line (both beams); return the task list path."""
    tasklist_dir = os.path.join(OUTPUT_BASE, "logs", step)
    os.makedirs(tasklist_dir, exist_ok=True)
    tasklist = os.path.join(tasklist_dir, "tasklist.txt")
    with open(tasklist, "w") as fh:
        for beam in BEAMS:
            for idx, f in enumerate(files):
                fh.write(task_command(step, beam, idx, f) + "\n")
    return tasklist


def make_slurm_script(step, tasklist, qos, dep=None):
    """Return (script_text, script_path) for a PyTaskFarmer SLURM job."""
    log_dir = os.path.join(OUTPUT_BASE, "logs", step)
    os.makedirs(log_dir, exist_ok=True)

    wall_time, nodes, workers, threads = STEP_RES[step]
    ptf_workdir = os.path.join(log_dir, "ptf_workdir")
    dep_line = f"#SBATCH --dependency=afterok:{dep}" if dep else ""

    script = f"""\
#!/bin/bash
#SBATCH --job-name=bib_{step}
#SBATCH --account={ACCOUNT}
#SBATCH --constraint={CONSTRAINT}
#SBATCH --qos={qos}
#SBATCH --time={wall_time}
#SBATCH --nodes={nodes}
#SBATCH --tasks-per-node=1
#SBATCH --output={log_dir}/slurm-%j.out
#SBATCH --error={log_dir}/slurm-%j.err
#SBATCH --signal=B:USR1@60
{dep_line}

# Forward USR1 to pytaskfarmer so it can checkpoint before the job ends.
function handle_signal {{
    echo "$(date) received USR1 - forwarding to pytaskfarmer (PID $PROCPID)"
    kill -s USR1 $PROCPID
    wait $PROCPID
}}
trap handle_signal USR1

echo "=== bib_{step} on $SLURM_JOB_NUM_NODES nodes, {workers} workers/node x {threads} threads ==="
echo "    Tasklist : {tasklist}"
echo "    PTF dir  : {ptf_workdir}"
echo "    Job ID   : $SLURM_JOB_ID"
date

srun --nodes=$SLURM_JOB_NUM_NODES \\
    python3 {PYTASKFARMER} \\
        --proc {workers} \\
        --workdir {ptf_workdir} \\
        {tasklist} &
PROCPID=$!
wait $PROCPID
RC=$?

echo "=== Done (exit $RC) ===" && date
exit $RC
"""
    script_path = os.path.join(log_dir, f"submit_{step}.sh")
    return script, script_path


def submit(step, script, path, dry_run):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(script)
    if dry_run:
        print(f"--- DRY RUN: {path} ---\n{script}")
        return "DRY_RUN"
    result = subprocess.run(
        ["sbatch", "--parsable", path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
    )
    if result.returncode != 0:
        sys.exit(f"sbatch failed:\n{result.stderr}")
    jobid = result.stdout.strip()
    print(f"Submitted {step}: job {jobid}  ({path})")
    return jobid


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--step", nargs="+", required=True, choices=STEP_ORDER + ["all"])
    parser.add_argument("--nfiles", type=int, default=None,
                        help="Limit to first N input files (default: all).")
    parser.add_argument("--depend", type=str, default=None,
                        help="SLURM job ID the first step should wait on.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print scripts without submitting.")
    args = parser.parse_args()

    steps = STEP_ORDER if "all" in args.step else [s for s in STEP_ORDER if s in args.step]
    files = discover_inputs()
    n     = args.nfiles or len(files)
    files = files[:n]
    qos   = QOS_TEST if n <= 10 else QOS_PROD

    for step_dir in ["GEN", "SIM", "DIGI", "RECO"]:
        for beam in BEAMS:
            os.makedirs(os.path.join(OUTPUT_BASE, step_dir, beam), exist_ok=True)

    print(f"Files: {n}  QOS: {qos}  Steps: {' -> '.join(steps)}  Beams: {' + '.join(BEAMS)}")

    prev = args.depend
    for step in steps:
        tasklist              = write_tasklist(step, files)
        wall, nodes, wk, thr  = STEP_RES[step]
        print(f"  {step}: {nodes} nodes x {wk} workers x {thr} threads  wall={wall}  tasklist={tasklist}")
        script, path = make_slurm_script(step, tasklist, qos, dep=prev)
        prev = submit(step, script, path, args.dry_run)

    print("\nDone. Resubmit the same command to retry unfinished tasks "
          "(PyTaskFarmer skips completed ones).")


if __name__ == "__main__":
    main()
