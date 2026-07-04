#!/usr/bin/env python3
"""benchmark_production.py - Summarise BIB production timing per step.

Reads each step's PyTaskFarmer timeline.json (logs/<step>/ptf_workdir/) and,
if present, the per-task GNU `time -v` logs (<output>.time.log), then prints a
per-step benchmark table: task counts, wall-clock span, per-task duration
statistics, aggregate CPU-hours, throughput and effective parallelism.

Usage:
    python benchmark_production.py                 # all steps, OUTPUT_BASE from config.sh
    python benchmark_production.py --step reco     # one step
    python benchmark_production.py --output-base /path/to/data --csv bench.csv
"""

import argparse
import glob
import json
import os
import re
import statistics as stats
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STEP_ORDER = ["gen", "sim", "digi", "reco"]


def config_output_base():
    """Best-effort read of OUTPUT_BASE from config.sh (no bash needed)."""
    cfg = os.path.join(SCRIPT_DIR, "config.sh")
    with open(cfg) as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("OUTPUT_BASE="):
                return line.split("=", 1)[1].partition("#")[0].strip().strip('"').strip("'")
    return None


def fmt_hms(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}"


def load_timeline(step, output_base):
    path = os.path.join(output_base, "logs", step, "ptf_workdir", "timeline.json")
    if not os.path.exists(path):
        return None, path
    with open(path) as fh:
        return json.load(fh), path


def max_rss_gib(step, output_base):
    """Peak 'Maximum resident set size' across per-task GNU time logs, in GiB."""
    pat = os.path.join(output_base, step.upper(), "*", f"bib_{step}_*.time.log")
    peak_kb = 0
    for logf in glob.glob(pat):
        try:
            with open(logf) as fh:
                for line in fh:
                    m = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", line)
                    if m:
                        peak_kb = max(peak_kb, int(m.group(1)))
        except OSError:
            continue
    return peak_kb / (1024 * 1024) if peak_kb else None


def summarise(step, output_base):
    timeline, path = load_timeline(step, output_base)
    if timeline is None:
        print(f"[{step:4}] no timeline.json ({path})")
        return None
    tasks = [r for r in timeline if r.get("cat") == "task" and "dur" in r]
    if not tasks:
        print(f"[{step:4}] timeline present but no task records")
        return None

    durs = sorted(r["dur"] / 1e6 for r in tasks)          # seconds
    starts = [r["ts"] / 1e6 for r in tasks]
    ends = [(r["ts"] + r["dur"]) / 1e6 for r in tasks]
    wall = max(ends) - min(starts)                         # wall-clock span, s
    cpu = sum(durs)                                        # aggregate task-seconds
    n = len(durs)
    workers = len({r.get("tid") for r in tasks})
    parallelism = cpu / wall if wall > 0 else float("nan")
    throughput = n / (wall / 3600) if wall > 0 else float("nan")  # tasks/hour

    def pct(p):
        return durs[min(n - 1, int(p / 100 * n))]

    rss = max_rss_gib(step, output_base)

    row = {
        "step": step, "tasks": n, "workers": workers,
        "wall_s": wall, "cpu_s": cpu,
        "mean_s": stats.mean(durs), "median_s": stats.median(durs),
        "min_s": durs[0], "max_s": durs[-1], "p95_s": pct(95),
        "parallelism": parallelism, "throughput_hr": throughput,
        "peak_rss_gib": rss,
    }

    print(f"\n=== {step.upper()} ===")
    print(f"  tasks completed : {n}")
    print(f"  workers seen    : {workers}")
    print(f"  wall-clock span : {fmt_hms(wall)}  ({wall:.0f} s)")
    print(f"  aggregate CPU   : {fmt_hms(cpu)}  ({cpu/3600:.1f} task-hours)")
    print(f"  per-task dur    : mean {row['mean_s']:.1f}s  median {row['median_s']:.1f}s  "
          f"min {row['min_s']:.1f}s  p95 {row['p95_s']:.1f}s  max {row['max_s']:.1f}s")
    print(f"  effective par.  : {parallelism:.1f}x concurrent tasks")
    print(f"  throughput      : {throughput:.0f} tasks/hour")
    if rss is not None:
        print(f"  peak RSS/task   : {rss:.2f} GiB")
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--step", nargs="+", choices=STEP_ORDER, default=STEP_ORDER)
    ap.add_argument("--output-base", default=None,
                    help="Production OUTPUT_BASE (default: read from config.sh)")
    ap.add_argument("--csv", default=None, help="Also write the summary as CSV.")
    args = ap.parse_args()

    output_base = args.output_base or config_output_base()
    if not output_base or not os.path.isdir(output_base):
        sys.exit(f"ERROR: OUTPUT_BASE not found: {output_base}")

    print(f"Benchmarking production under: {output_base}")
    rows = [r for r in (summarise(s, output_base) for s in args.step) if r]

    if rows:
        tot_cpu = sum(r["cpu_s"] for r in rows)
        tot_wall = sum(r["wall_s"] for r in rows)
        print(f"\n--- totals over {len(rows)} step(s) ---")
        print(f"  summed wall-clock : {fmt_hms(tot_wall)}")
        print(f"  summed CPU        : {fmt_hms(tot_cpu)}  ({tot_cpu/3600:.1f} task-hours)")

    if args.csv and rows:
        import csv
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nWrote CSV: {args.csv}")


if __name__ == "__main__":
    main()
