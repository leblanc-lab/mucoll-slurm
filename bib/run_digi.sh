#!/bin/bash
# ============================================================================
# BIB DIGI Step (v3.1): Digitization via k4run
# ============================================================================
# Usage: bash run_digi.sh <input_sim.edm4hep.root> <output_digi.edm4hep.root>
#                         <benchmarks_path> <detector_geom> [num_threads]
# Runs INSIDE the container (called via Shifter from PyTaskFarmer).
# ============================================================================
set -eo pipefail

INPUT_FILE="${1:?Usage: run_digi.sh <input.edm4hep.root> <output.edm4hep.root> <benchmarks_path> <detector_geom> [num_threads]}"
OUTPUT_FILE="${2:?}"
MUCOLL_BENCHMARKS="${3:?}"
DETECTOR_GEOM="${4:-MAIA_v0}"
NUM_THREADS="${5:-1}"

echo "=========================================="
echo " BIB DIGI Step (v3.1)"
echo " Input:   ${INPUT_FILE}"
echo " Output:  ${OUTPUT_FILE}"
echo " Geom:    ${DETECTOR_GEOM}"
echo " Threads: ${NUM_THREADS}"
echo " Host:    $(hostname)"
echo "=========================================="

# --- Container software stack (v3.1 official entry point, glob fallback) -----
if [[ -f /opt/setup_mucoll.sh ]]; then
    source /opt/setup_mucoll.sh
else
    STACK_SETUP=$(find /opt/spack/opt/spack -maxdepth 8 -path "*/linux-*/mucoll-stack-*/setup.sh" 2>/dev/null | sort | tail -n 1)
    [[ -n "$STACK_SETUP" ]] || { echo "ERROR: no mucoll stack setup found in container" >&2; exit 1; }
    source "$STACK_SETUP"
fi

# Detector geometry + config PYTHONPATH (exports MUCOLL_CONFIG, MUCOLL_CONFIG_NAME).
# setup_config.sh uses `find ... | head -n1`; head closes the pipe early and
# find gets SIGPIPE, which under `pipefail` intermittently returns 141 and
# aborts the step. Disable pipefail across the source (set -e still catches a
# genuine `return 1` from a failed geometry lookup).
set +o pipefail
source "${MUCOLL_BENCHMARKS}/setup_config.sh" "${MUCOLL_BENCHMARKS}" "${DETECTOR_GEOM}"
set -o pipefail

mkdir -p "$(dirname "${OUTPUT_FILE}")"

# Isolated scratch cwd (digi_histograms.root is written to cwd).
SCRATCH="/tmp/bib_digi_$$_${RANDOM}"
mkdir -p "${SCRATCH}"; cd "${SCRATCH}"
trap 'cd /; rm -rf "${SCRATCH}"' EXIT

TIMED=()
[[ -x /usr/bin/time ]] && TIMED=(/usr/bin/time -v -o "${OUTPUT_FILE}.time.log" --)

CMD=(k4run "${MUCOLL_CONFIG}/${MUCOLL_CONFIG_NAME}/digi_steer.py"
     --inputFiles "${INPUT_FILE}"
     --outputFile "${OUTPUT_FILE}"
     --numThreads "${NUM_THREADS}")

echo "Running: ${CMD[*]}"
"${TIMED[@]}" "${CMD[@]}"

echo "DIGI step complete: ${OUTPUT_FILE}"
