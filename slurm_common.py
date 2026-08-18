"""Shared helpers for the mucoll-slurm submission scripts.

Everything configurable lives in ``config.sh``.
This module loads it once and provides the small amount of glue needed to build
an ``apptainer exec`` command and submit a SLURM job.
"""

import os
import shlex
import subprocess

REPO_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIG_SH = os.path.join(REPO_DIR, "config.sh")

# Keys exported by config.sh that the Python submitters care about.
_CONFIG_KEYS = [
    "WORK_DIR",
    "MUCOLL_BENCHMARKS_PATH",
    "DATA_GROUP_DIR",
    "IMAGE",
    "WHIZARD_IMAGE",
    "GEOM_NAME",
    "OUTPUT_BASE_DIR",
    "DATA_BIND",
    "BIB_DIR",
    "BIB_MUPLUS",
    "BIB_MUMINUS",
    "BIB_NUMBER",
]


def load_config(config_path=CONFIG_SH):
    """Source ``config.sh`` in a subshell and return its exports as a dict.

    Using bash to evaluate the file keeps it the single source of truth (no
    duplicated values in Python) and lets it auto-detect paths and use $USER.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"config.sh not found at {config_path} -- copy/edit it first."
        )
    # Paths never contain newlines, so newline-delimited KEY=VALUE is safe.
    echoes = "\n".join(f'echo "{k}=${{{k}}}"' for k in _CONFIG_KEYS)
    script = f"set -e\nsource {shlex.quote(config_path)}\n{echoes}\n"
    out = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=True
    ).stdout
    cfg = {}
    for line in out.splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            cfg[key] = val
    missing = [k for k in _CONFIG_KEYS if not cfg.get(k)]
    if missing:
        raise RuntimeError(f"config.sh did not set: {', '.join(missing)}")
    return cfg


def validate_paths(cfg):
    """Fail fast with a clear message if the checkout or image is missing."""
    if not os.path.isdir(cfg["MUCOLL_BENCHMARKS_PATH"]):
        raise SystemExit(
            f"Error: mucoll-benchmarks not found at {cfg['MUCOLL_BENCHMARKS_PATH']}.\n"
            "Check it out as a sibling of mucoll-slurm (see README.md)."
        )
    if not os.path.exists(cfg["IMAGE"]):
        raise SystemExit(
            f"Error: container image not found at {cfg['IMAGE']}.\n"
            "Pull the v3.1 image first (see README.md) or fix IMAGE in config.sh."
        )


def apptainer_cmd(cfg, chain_script, chain_args, image=None):
    """Build the ``apptainer exec ... bash <chain_script> <args>`` command.

    ``image`` overrides ``cfg['IMAGE']`` (e.g. a Whizard-capable image).
    """
    args = " ".join(shlex.quote(str(a)) for a in chain_args)
    return (
        f"apptainer exec --bind {cfg['DATA_BIND']},{cfg['WORK_DIR']} "
        f"{shlex.quote(image or cfg['IMAGE'])} bash {shlex.quote(chain_script)} {args}"
    )


def make_slurm_script(job_name, out_log, err_log, sbatch_directives, body):
    """Assemble a SLURM batch script.

    ``sbatch_directives`` is a list of strings like ``"--time=08:00:00"``.
    """
    header = [
        "#!/bin/bash",
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --output={out_log}",
        f"#SBATCH --error={err_log}",
    ]
    header += [f"#SBATCH {d}" for d in sbatch_directives]
    return "\n".join(header) + "\n\n" + body + "\n"


def submit(slurm_script_text, tmp_name):
    """Write a temp SLURM script, ``sbatch`` it, and clean up. Returns ok/fail."""
    tmp_path = os.path.join(REPO_DIR, tmp_name)
    with open(tmp_path, "w") as f:
        f.write(slurm_script_text)
    try:
        result = subprocess.run(
            ["sbatch", tmp_path], capture_output=True, text=True, check=True
        )
        print(f"  {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("  Error: 'sbatch' not found -- are you on an Oscar login node?")
        return False
    except subprocess.CalledProcessError as e:
        print(f"  Error submitting {tmp_name}: {e.stderr.strip()}")
        return False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
