#!/bin/bash
# ============================================================================
# BIB GEN Step (v3.0): FLUKA binary -> EDM4HEP MCParticles
# ============================================================================
# Usage: bash run_gen.sh <input.dat> <output.edm4hep.root> <benchmarks_path>
#                        [bx_time] [normalization] [extra flags...]
# Runs INSIDE the container (called via Shifter from PyTaskFarmer).
# ============================================================================
set -eo pipefail

INPUT_FILE="${1:?Usage: run_gen.sh <input.dat> <output.edm4hep.root> <benchmarks_path>}"
OUTPUT_FILE="${2:?}"
MUCOLL_BENCHMARKS="${3:?}"
BX_TIME="${4:-0.0}"
NORMALIZATION="${5:-1.0}"
shift 5
EXTRA_FLAGS=("$@")   # pre-built optional flags from submit_bib.py (-z, --pdgs, ...)

echo "=========================================="
echo " BIB GEN Step (v3.0)"
echo " Input:  ${INPUT_FILE}"
echo " Output: ${OUTPUT_FILE}"
echo " Extra:  ${EXTRA_FLAGS[*]:-(none)}"
echo " Host:   $(hostname)"
echo "=========================================="

# --- Container software stack (v3.0 official entry point, glob fallback) -----
if [[ -f /opt/setup_mucoll.sh ]]; then
    source /opt/setup_mucoll.sh
else
    STACK_SETUP=$(find /opt/spack/opt/spack -maxdepth 8 -path "*/linux-*/mucoll-stack-*/setup.sh" 2>/dev/null | sort | tail -n 1)
    [[ -n "$STACK_SETUP" ]] || { echo "ERROR: no mucoll stack setup found in container" >&2; exit 1; }
    source "$STACK_SETUP"
fi

# bib_pdgs.py lives alongside fluka_to_edm4hep.py
export PYTHONPATH="${MUCOLL_BENCHMARKS}/generation/bib${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$(dirname "${OUTPUT_FILE}")"

# Timing wrapper for benchmarking (per-task resource usage).
TIMED=()
[[ -x /usr/bin/time ]] && TIMED=(/usr/bin/time -v -o "${OUTPUT_FILE}.time.log" --)

CMD=(python3 "${MUCOLL_BENCHMARKS}/generation/bib/fluka_to_edm4hep.py"
     "${INPUT_FILE}" "${OUTPUT_FILE}"
     -b "${BX_TIME}" -n "${NORMALIZATION}" -o
     "${EXTRA_FLAGS[@]}")

echo "Running: ${CMD[*]}"
"${TIMED[@]}" "${CMD[@]}"

echo "GEN step complete: ${OUTPUT_FILE}"
