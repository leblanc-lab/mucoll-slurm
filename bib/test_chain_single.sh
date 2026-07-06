#!/bin/bash
# ============================================================================
# test_chain_single.sh - One-file GEN -> SIM -> DIGI -> RECO smoke test
# ============================================================================
# Runs a SINGLE FLUKA file through the full chain using the exact same
# run_*.sh scripts, container image, geometry and thread counts that the batch
# jobs use (all read from config.sh). Run this on a login node BEFORE launching
# the full production to confirm the v3.0 image and every step work end to end.
#
# Usage:
#   bash mucoll-slurm/bib/test_chain_single.sh [FLUKA_INDEX]
#
#   FLUKA_INDEX  which discovered FLUKA file to use (default: 0)
# ============================================================================
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

IDX="${1:-0}"

# Pick the IDX-th FLUKA summary file (sorted, same order submit_bib.py uses).
mapfile -t FLUKA_FILES < <(ls "${FLUKA_INPUT_DIR}"/summary*_DET_IP.dat 2>/dev/null | sort)
if [[ "${#FLUKA_FILES[@]}" -eq 0 ]]; then
    echo "ERROR: no summary*_DET_IP.dat files in ${FLUKA_INPUT_DIR}" >&2
    exit 1
fi
INPUT="${FLUKA_FILES[$IDX]:?index $IDX out of range (have ${#FLUKA_FILES[@]} files)}"

TESTDIR="${OUTPUT_BASE}/test_chain"
GEN="${TESTDIR}/gen.edm4hep.root"
SIM="${TESTDIR}/sim.edm4hep.root"
DIGI="${TESTDIR}/digi.edm4hep.root"
RECO="${TESTDIR}/reco.edm4hep.root"

echo "=============================================================="
echo " BIB full-chain smoke test (v3.0)"
echo "   Image      : ${CONTAINER_IMAGE}"
echo "   Benchmarks : ${MUCOLL_BENCHMARKS}"
echo "   Geometry   : ${DETECTOR_GEOM}"
echo "   FLUKA input: ${INPUT}"
echo "   Test outdir: ${TESTDIR}"
echo "   DIGI thr=${DIGI_THREADS}  RECO thr=${RECO_THREADS}"
echo "=============================================================="

mkdir -p "${TESTDIR}"
rm -f "${GEN}" "${SIM}" "${DIGI}" "${RECO}"

# GEN optional flags, mirroring submit_bib.py (MUPLUS beam -> no -z).
GEN_EXTRA=()
[[ -n "${GEN_T_MAX}"  ]] && GEN_EXTRA+=(--t_max  "${GEN_T_MAX}")
[[ -n "${GEN_NE_MIN}" ]] && GEN_EXTRA+=(--ne_min "${GEN_NE_MIN}")

run_step() {
    local name="$1"; shift
    local log="${TESTDIR}/${name}.log"
    echo
    echo ">>> [${name}] $*"
    echo "    log: ${log}"
    echo
    # Redirect step output to a log file (as PyTaskFarmer does on the batch
    # system) instead of streaming to the terminal. The steering file forces
    # ddsim to print ~1000+ lines/event, and if the terminal reader goes away
    # (piped through head/less, ssh hiccup) the step dies with SIGPIPE (141).
    local rc=0
    shifter --image="${CONTAINER_IMAGE}" bash "$@" >"${log}" 2>&1 || rc=$?
    if [[ $rc -ne 0 ]]; then
        echo "❌ ${name} FAILED (rc=${rc}). Last 40 lines of ${log}:"
        tail -n 40 "${log}"
        exit 1
    fi
    echo "    ${name} done ($(wc -l <"${log}") log lines)"
}

check() {
    local name="$1" f="$2"
    if [[ -s "$f" ]]; then
        echo "✅ ${name} OK -> $(ls -lh "$f" | awk '{print $5}')  ${f}"
    else
        echo "❌ ${name} produced no output: ${f}"; exit 1
    fi
}

run_step GEN  "${SCRIPT_DIR}/run_gen.sh"  "${INPUT}" "${GEN}"  "${MUCOLL_BENCHMARKS}" \
              "${GEN_BX_TIME}" "${GEN_NORMALIZATION}" "${GEN_EXTRA[@]}"
check   GEN  "${GEN}"

run_step SIM  "${SCRIPT_DIR}/run_sim.sh"  "${GEN}"  "${SIM}"  "${MUCOLL_BENCHMARKS}" "${DETECTOR_GEOM}"
check   SIM  "${SIM}"

run_step DIGI "${SCRIPT_DIR}/run_digi.sh" "${SIM}"  "${DIGI}" "${MUCOLL_BENCHMARKS}" "${DETECTOR_GEOM}" "${DIGI_THREADS}"
check   DIGI "${DIGI}"

run_step RECO "${SCRIPT_DIR}/run_reco.sh" "${DIGI}" "${RECO}" "${MUCOLL_BENCHMARKS}" "${DETECTOR_GEOM}" "${RECO_THREADS}"
check   RECO "${RECO}"

echo
echo "=============================================================="
echo " ✅ FULL CHAIN PASSED"
echo "    Per-step timing logs (GNU time -v):"
for f in "${GEN}" "${SIM}" "${DIGI}" "${RECO}"; do
    [[ -f "${f}.time.log" ]] && printf "      %-5s %s\n" "$(basename "${f%%.*}")" "${f}.time.log"
done
echo
echo " If this looks good, launch the production with:"
echo "   cd ${SCRIPT_DIR}"
echo "   python submit_bib.py --step all            # full chain, all files"
echo "   python submit_bib.py --step gen --nfiles 4 # small test batch first"
echo "=============================================================="
