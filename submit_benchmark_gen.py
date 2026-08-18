#!/usr/bin/env python3
"""Submit one NERSC debug-QoS job to make the benchmark GEN input files."""

import argparse
import os
import pathlib
import shlex
import subprocess


REPO_DIR = pathlib.Path(__file__).resolve().parent
WORK_DIR = REPO_DIR.parent
BENCHMARKS_DIR = WORK_DIR / "mucoll-benchmarks"
CHAIN = REPO_DIR / "chains" / "run_benchmark_gen.sh"

DEFAULT_IMAGE = "ghcr.io/muoncollidersoft/mucoll-analysis-ubuntu24:v3.1"
DEFAULT_IMAGE_DIGEST = (
    "sha256:7fc8a1c880b252fa84528a976916c1b0c14a80d276c3aec00cd7427a65d913f1"
)
DEFAULT_OUTPUT = (
    "/global/cfs/cdirs/m5197/mleblanc/MuonCollider/data/benchmark-inputs/v1"
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    parser.add_argument("--events", type=int, default=10_000)
    parser.add_argument("--version", default="v1")
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--image-digest", default=DEFAULT_IMAGE_DIGEST)
    parser.add_argument("--account", default="m5197")
    parser.add_argument("--qos", default="debug")
    parser.add_argument("--constraint", default="cpu")
    parser.add_argument("--time", default="00:10:00")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def git_revision(repo):
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    ).stdout
    return sha + ("-dirty" if status else "")


def shell_join(arguments):
    """Return a shell-safe command string (compatible with Python 3.6)."""
    return " ".join(shlex.quote(str(argument)) for argument in arguments)


def main():
    args = parse_args()
    if args.events <= 0:
        raise SystemExit("--events must be positive")
    if not CHAIN.is_file() or not BENCHMARKS_DIR.is_dir():
        raise SystemExit(
            "mucoll-slurm and mucoll-benchmarks must be sibling checkouts under "
            f"{WORK_DIR}"
        )

    output_dir = pathlib.Path(args.output_dir).expanduser().resolve()
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    benchmark_sha = git_revision(BENCHMARKS_DIR)
    command = [
        "shifter",
        f"--image={args.image}",
        "bash",
        str(CHAIN),
        str(output_dir),
        str(args.events),
        args.version,
        str(args.seed),
        args.image,
        args.image_digest,
        benchmark_sha,
    ]

    job_script = log_dir / "submit_gen_inputs.sh"
    script = f"""#!/bin/bash
#SBATCH --job-name=mucoll_gen_inputs
#SBATCH --account={args.account}
#SBATCH --constraint={args.constraint}
#SBATCH --qos={args.qos}
#SBATCH --time={args.time}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output={log_dir}/slurm-%j.out
#SBATCH --error={log_dir}/slurm-%j.err

set -euo pipefail
{shell_join(command)}
"""
    job_script.write_text(script, encoding="utf-8")

    print(f"Image:      {args.image}@{args.image_digest}")
    print(f"Benchmarks: {benchmark_sha}")
    print(f"Output:     {output_dir}")
    print(f"Workload:   4 particles x {args.events} events")
    print(f"Slurm:      account={args.account} qos={args.qos} time={args.time}")
    print("Runtime:    shifter")
    print(f"Job script: {job_script}")

    if args.dry_run:
        print("\n" + script)
        return

    result = subprocess.run(
        ["sbatch", "--parsable", str(job_script)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    print(f"Submitted job {result.stdout.strip()}")


if __name__ == "__main__":
    main()
