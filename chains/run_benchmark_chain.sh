#!/bin/bash
# Run a fixed GEN benchmark input through SIM -> DIGI -> RECO.
# This script runs inside the mucoll-sim container.
set -euo pipefail

INPUT_FILE="${1:?usage: run_benchmark_chain.sh INPUT OUTPUT_DIR EVENTS GEOMETRY}"
OUTPUT_DIR="${2:?}"
EVENTS="${3:-10}"
GEOMETRY="${4:-MAIA_v0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BENCHMARKS_DIR="${WORK_DIR}/mucoll-benchmarks"
SPACK_DIR="${WORK_DIR}/mucoll-spack"
CHAIN="${SPACK_DIR}/validation/run_chain.sh"

if [[ ! -f "${INPUT_FILE}" ]]; then
    echo "ERROR: GEN input not found: ${INPUT_FILE}" >&2
    exit 1
fi
if [[ ! -f "${CHAIN}" ]]; then
    echo "ERROR: validation chain not found: ${CHAIN}" >&2
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"
for stage in sim digi reco; do
    if [[ -e "${OUTPUT_DIR}/${stage}.edm4hep.root" ]]; then
        echo "ERROR: refusing to overwrite ${OUTPUT_DIR}/${stage}.edm4hep.root" >&2
        exit 1
    fi
done

SCRATCH_BASE="${SCRATCH:-/tmp}"
RUN_DIR="$(mktemp -d "${SCRATCH_BASE}/mucoll-benchmark-${SLURM_JOB_ID:-local}-XXXXXX")"
cleanup() {
    rm -rf -- "${RUN_DIR}"
}
trap cleanup EXIT

cp "${INPUT_FILE}" "${RUN_DIR}/gen.edm4hep.root"
cd "${RUN_DIR}"

export BM="${BENCHMARKS_DIR}"
export GEOM="${GEOMETRY}"
export NEV="${EVENTS}"

echo "Benchmark smoke chain"
echo "  input   : ${INPUT_FILE}"
echo "  output  : ${OUTPUT_DIR}"
echo "  events  : ${EVENTS}"
echo "  geometry: ${GEOMETRY}"
echo "  scratch : ${RUN_DIR}"

for stage in sim digi reco; do
    echo "--- ${stage^^} ---"
    bash "${CHAIN}" "${stage}"
    cp "${stage}.edm4hep.root" "${OUTPUT_DIR}/${stage}.edm4hep.root"
done

echo "Benchmark smoke chain complete"
ls -lh "${OUTPUT_DIR}"/*.edm4hep.root
