#!/bin/bash
# =============================================================================
#  Particle-gun chain: GEN -> SIM -> DIGI -> RECO  (runs inside the container)
# =============================================================================
#  Named arguments (order independent):
#     --job-id N        job index (used in output file names)        [required]
#     --nevents N       number of events                             [default 100]
#     --outdir DIR      output directory (job_N/ is created inside)  [required]
#     --pdg N           particle PDG id (11 e, 13 mu, 211 pi, ...)   [default 13]
#     --pt V            transverse momentum [GeV]                    [default 100]
#     --theta-min V     min polar angle [deg]                        [default 10]
#     --theta-max V     max polar angle [deg]                        [default 170]
#     --bib             enable Beam-Induced Background overlay in DIGI [off]
#     --seed N          random seed for GEN and DIGI          [default 1234 + job-id]
#
#  Paths (image, benchmarks, geometry, BIB samples) come from ../config.sh.
# =============================================================================
set -e

# Defaults
JOB_ID=""
NEVENTS=100
OUTPUT_DIR=""
PDG=13
PT=100
THETA_MIN=10
THETA_MAX=170
DO_BIB=0
SEED=""

while [ $# -gt 0 ]; do
    case "$1" in
        --job-id)     JOB_ID="$2";     shift 2 ;;
        --nevents)    NEVENTS="$2";    shift 2 ;;
        --outdir)     OUTPUT_DIR="$2"; shift 2 ;;
        --pdg)        PDG="$2";        shift 2 ;;
        --pt)         PT="$2";         shift 2 ;;
        --theta-min)  THETA_MIN="$2";  shift 2 ;;
        --theta-max)  THETA_MAX="$2";  shift 2 ;;
        --bib)        DO_BIB=1;        shift 1 ;;
        --seed)       SEED="$2";       shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$JOB_ID" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "ERROR: --job-id and --outdir are required." >&2
    exit 1
fi
# Every job needs its own seed, otherwise all jobs generate identical events.
SEED="${SEED:-$((1234 + JOB_ID))}"

# --- Resolve repo location and load shared config / environment --------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
source "$SCRIPT_DIR/../config.sh"           # WORK_DIR, MUCOLL_BENCHMARKS_PATH, BIB_*, GEOM_NAME
source "$SCRIPT_DIR/../scripts/setup.sh"     # spack stack (glob-based)
# Detector geometry + PYTHONPATH for the digi/reco steering files.
# (setup_config.sh exports MUCOLL_GEO, MUCOLL_CONFIG, MUCOLL_CONFIG_NAME, PYTHONPATH)
source "$MUCOLL_BENCHMARKS_PATH/setup_config.sh" "$MUCOLL_BENCHMARKS_PATH" "$GEOM_NAME"

echo "=== pgun chain: job $JOB_ID, $NEVENTS events ==="
echo "Particle: PDG=$PDG, pT=$PT GeV, theta=[$THETA_MIN, $THETA_MAX], BIB=$DO_BIB, seed=$SEED"
echo "Output:   $OUTPUT_DIR/job_${JOB_ID}"

# --- Scratch working directory ----------------------------------------------
WORKDIR=/tmp/mucoll_job_${JOB_ID}_${RANDOM}
mkdir -p "$WORKDIR"
cd "$WORKDIR"
echo "Working in $WORKDIR"

# Pandora needs its settings in the cwd.
cp -r "$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/PandoraSettings/" ./

# --- 1. Generation -----------------------------------------------------------
echo "--- Generation ---"
python "$MUCOLL_BENCHMARKS_PATH/generation/pgun/pgun_edm4hep.py" \
    -p 1 -e "$NEVENTS" -s "$SEED" --pdg "$PDG" --pt "$PT" --theta "$THETA_MIN" "$THETA_MAX" \
    -- gen_output.edm4hep.root

# --- 2. Simulation -----------------------------------------------------------
echo "--- Simulation ---"
ddsim --steeringFile "$MUCOLL_BENCHMARKS_PATH/simulation/steer_baseline.py" \
    --numberOfEvents "$NEVENTS" \
    --inputFiles gen_output.edm4hep.root \
    --outputFile sim_output.edm4hep.root

# --- 3. Digitization (optionally with BIB overlay) ---------------------------
echo "--- Digitization (BIB=$DO_BIB) ---"
DIGI_BIB_ARGS=()
if [ "$DO_BIB" -eq 1 ]; then
    DIGI_BIB_ARGS=(--doOverlayFull
                   --OverlayFullPathToMuPlus "$BIB_MUPLUS"
                   --OverlayFullPathToMuMinus "$BIB_MUMINUS"
                   --OverlayFullNumberBackground "$BIB_NUMBER")
fi
k4run "$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/digi_steer.py" \
    -n -1 \
    --inputFiles sim_output.edm4hep.root \
    --outputFile digi_output.edm4hep.root \
    --RandSeed "$SEED" \
    "${DIGI_BIB_ARGS[@]}"

# --- 4. Reconstruction -------------------------------------------------------
echo "--- Reconstruction ---"
k4run "$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/reco_steer.py" \
    -n -1 \
    --inputFiles digi_output.edm4hep.root \
    --outputFile reco_output.edm4hep.root

# --- Collect outputs ---------------------------------------------------------
FINAL_OUT_DIR="$OUTPUT_DIR/job_${JOB_ID}"
mkdir -p "$FINAL_OUT_DIR"
echo "Moving outputs to $FINAL_OUT_DIR"
for stage in gen sim digi reco; do
    mv "${stage}_output.edm4hep.root" "$FINAL_OUT_DIR/${stage}_output_${JOB_ID}.edm4hep.root"
done

cd /
rm -rf "$WORKDIR"
echo "Job $JOB_ID finished successfully"
