#!/usr/bin/env python3
"""Submit a small GEN -> SIM -> DIGI -> RECO benchmark smoke test on NERSC."""

import argparse
import hashlib
import json
import pathlib
import shlex
import subprocess


REPO_DIR = pathlib.Path(__file__).resolve().parent
WORK_DIR = REPO_DIR.parent
BENCHMARKS_DIR = WORK_DIR / "mucoll-benchmarks"
SPACK_DIR = WORK_DIR / "mucoll-spack"
CHAIN = REPO_DIR / "chains" / "run_benchmark_chain.sh"

DATA_ROOT = pathlib.Path(
    "/global/cfs/cdirs/m5197/mleblanc/MuonCollider/data"
)
DEFAULT_INPUT = DATA_ROOT / "benchmark-inputs/v1/gen-muon-v1.edm4hep.root"
DEFAULT_OUTPUT = DATA_ROOT / "benchmark-runs/smoke-muon-v1"
DEFAULT_IMAGE = "ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:v3.1"
DEFAULT_IMAGE_DIGEST = (
    "sha256:fb6c93101b0bb0931c8285b00782cc16d69021e4011ddc5b672bc61136e9725a"
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--events", type=int, default=10)
    parser.add_argument("--geometry", default="MAIA_v0")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--image-digest", default=DEFAULT_IMAGE_DIGEST)
    parser.add_argument("--account", default="m5197")
    parser.add_argument("--qos", default="debug")
    parser.add_argument("--constraint", default="cpu")
    parser.add_argument("--time", default="00:30:00")
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


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shell_join(arguments):
    return " ".join(shlex.quote(str(argument)) for argument in arguments)


def main():
    args = parse_args()
    if args.events <= 0:
        raise SystemExit("--events must be positive")

    input_file = pathlib.Path(args.input).expanduser().resolve()
    output_dir = pathlib.Path(args.output_dir).expanduser().resolve()
    if not input_file.is_file():
        raise SystemExit(f"GEN input not found: {input_file}")
    for path in (CHAIN, BENCHMARKS_DIR, SPACK_DIR):
        if not path.exists():
            raise SystemExit(f"Required checkout path not found: {path}")
    for stage in ("sim", "digi", "reco"):
        if (output_dir / f"{stage}.edm4hep.root").exists():
            raise SystemExit(f"Refusing to overwrite existing {stage} output")

    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    revisions = {
        "mucoll_benchmarks": git_revision(BENCHMARKS_DIR),
        "mucoll_slurm": git_revision(REPO_DIR),
        "mucoll_spack": git_revision(SPACK_DIR),
    }
    metadata = {
        "schema_version": 1,
        "input": {"path": str(input_file), "sha256": sha256(input_file)},
        "events": args.events,
        "geometry": args.geometry,
        "container": {"reference": args.image, "digest": args.image_digest},
        "revisions": revisions,
        "slurm": {
            "account": args.account,
            "qos": args.qos,
            "constraint": args.constraint,
            "time": args.time,
        },
    }
    (output_dir / "submission.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    command = [
        "shifter",
        f"--image={args.image}",
        "bash",
        str(CHAIN),
        str(input_file),
        str(output_dir),
        str(args.events),
        args.geometry,
    ]
    job_script = log_dir / "submit_chain.sh"
    script = f"""#!/bin/bash
#SBATCH --job-name=mucoll_benchmark_smoke
#SBATCH --account={args.account}
#SBATCH --constraint={args.constraint}
#SBATCH --qos={args.qos}
#SBATCH --time={args.time}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --output={log_dir}/slurm-%j.out
#SBATCH --error={log_dir}/slurm-%j.err

set -euo pipefail
{shell_join(command)}
"""
    job_script.write_text(script, encoding="utf-8")

    print(f"Input:      {input_file}")
    print(f"Output:     {output_dir}")
    print(f"Image:      {args.image}@{args.image_digest}")
    print(f"Events:     {args.events}")
    print(f"Geometry:   {args.geometry}")
    print(f"Slurm:      account={args.account} qos={args.qos} time={args.time}")
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
