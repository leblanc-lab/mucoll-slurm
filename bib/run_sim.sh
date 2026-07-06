#!/bin/bash
# ============================================================================
# BIB SIM Step (v3.0): Geant4 detector simulation via ddsim
# ============================================================================
# Usage: bash run_sim.sh <input_gen.edm4hep.root> <output_sim.edm4hep.root>
#                        <benchmarks_path> <detector_geom>
# Runs INSIDE the container (called via Shifter from PyTaskFarmer).
# ============================================================================
set -eo pipefail

INPUT_FILE="${1:?Usage: run_sim.sh <input.edm4hep.root> <output.edm4hep.root> <benchmarks_path> <detector_geom>}"
OUTPUT_FILE="${2:?}"
MUCOLL_BENCHMARKS="${3:?}"
DETECTOR_GEOM="${4:-MAIA_v0}"

echo "=========================================="
echo " BIB SIM Step (v3.0)"
echo " Input:  ${INPUT_FILE}"
echo " Output: ${OUTPUT_FILE}"
echo " Geom:   ${DETECTOR_GEOM}"
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

# Detector geometry (exports MUCOLL_GEO used by the steering file).
# setup_config.sh uses `find ... | head -n1`; head closes the pipe early and
# find gets SIGPIPE, which under `pipefail` intermittently returns 141 and
# aborts the step. Disable pipefail across the source (set -e still catches a
# genuine `return 1` from a failed geometry lookup).
set +o pipefail
source "${MUCOLL_BENCHMARKS}/setup_config.sh" "${MUCOLL_BENCHMARKS}" "${DETECTOR_GEOM}"
set -o pipefail

mkdir -p "$(dirname "${OUTPUT_FILE}")"

# Isolated scratch cwd so parallel PTF workers don't collide on cwd artifacts.
SCRATCH="/tmp/bib_sim_$$_${RANDOM}"
mkdir -p "${SCRATCH}"; cd "${SCRATCH}"
trap 'cd /; rm -rf "${SCRATCH}"' EXIT

TIMED=()
[[ -x /usr/bin/time ]] && TIMED=(/usr/bin/time -v -o "${OUTPUT_FILE}.time.log" --)

# BIB GEN writes exactly one event per file (one bunch crossing). We simulate
# that single event explicitly: v3.0's podio throws "reading beyond bounds" if
# ddsim is told to read all events (-1) and steps past the last frame.
CMD=(ddsim --steeringFile "${MUCOLL_BENCHMARKS}/simulation/steer_baseline.py"
     --numberOfEvents 1
     --inputFiles "${INPUT_FILE}"
     --outputFile "${OUTPUT_FILE}")

echo "Running: ${CMD[*]}"
"${TIMED[@]}" "${CMD[@]}"

echo "SIM step complete: ${OUTPUT_FILE}"
