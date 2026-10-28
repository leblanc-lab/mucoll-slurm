#!/bin/bash
set -e

# Arguments
JOB_ID=$1
NEVENTS=$2
OUTPUT_DIR=$3
MUCOLL_BENCHMARKS_PATH=$4
CARD=$5          # Pythia8 card, e.g. mumu_Z_hadrons_10TeV.cmnd (looked up in pythia/)
LABEL=${6:-""}   # suffix for the job output directory (default: card name)

if [ -z "$CARD" ]; then
    echo "Usage: $0 JOB_ID NEVENTS OUTPUT_DIR MUCOLL_BENCHMARKS_PATH CARD [LABEL]" >&2
    exit 1
fi
LABEL=${LABEL:-$(basename "$CARD" .cmnd)}

echo "Starting job $JOB_ID with $NEVENTS events"
echo "Output directory: $OUTPUT_DIR"
echo "Benchmarks path: $MUCOLL_BENCHMARKS_PATH"
echo "Pythia8 card: $CARD"

# Load shared config + spack environment (glob-based, image-version agnostic).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
source "$SCRIPT_DIR/../config.sh"
source "$SCRIPT_DIR/../scripts/setup.sh"

# Setup detector geometry and PYTHONPATH for digi/reco steering files.
source "$MUCOLL_BENCHMARKS_PATH/setup_config.sh" "$MUCOLL_BENCHMARKS_PATH" "$GEOM_NAME"

# Pythia8 and HepMC3 are provided by the v3.1 sim image's generator layer.
if ! command -v pythia8-config >/dev/null 2>&1 || ! command -v HepMC3-config >/dev/null 2>&1; then
    echo "ERROR: Pythia8/HepMC3 not found in this image (need pythia8-config" >&2
    echo "       and HepMC3-config) -- use a v3.1 (or newer) sim image." >&2
    exit 1
fi

# Resolve the card: a bare name is taken from this repo's pythia/ directory.
[ -f "$CARD" ] || CARD="$SCRIPT_DIR/../pythia/$CARD"
if [ ! -f "$CARD" ]; then
    echo "ERROR: Pythia8 card not found: $CARD" >&2
    exit 1
fi

# Create a temporary working directory
WORKDIR=/tmp/mucoll_job_${JOB_ID}_${RANDOM}
mkdir -p $WORKDIR
cd $WORKDIR
echo "Working in $WORKDIR"

# Copy PandoraSettings needed for reconstruction
cp -r "$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/PandoraSettings/" ./

# --- 1. Generation (Pythia8) ---
echo "Running Generation..."
# Build the small Pythia8 -> HepMC3 driver (kept in this repo; takes ~10 s).
g++ "$SCRIPT_DIR/../pythia/pythia_hepmc3.cc" -o pythia_hepmc3 \
    $(pythia8-config --cxxflags --ldflags) \
    $(HepMC3-config --cflags --libs) -Wl,-rpath,$(HepMC3-config --libdir)
cp "$CARD" ./job.cmnd

# Seed and event count are passed on the command line (override the card).
./pythia_hepmc3 job.cmnd gen_output.hepmc $NEVENTS $((1234 + JOB_ID))

# --- 2. Simulation ---
echo "Running Simulation..."
# ddsim can read hepmc directly.
ddsim --steeringFile $MUCOLL_BENCHMARKS_PATH/simulation/steer_baseline.py \
    --numberOfEvents $NEVENTS \
    --inputFiles gen_output.hepmc \
    --outputFile sim_output.edm4hep.root

# --- 3. Digitization ---
echo "Running Digitization..."
k4run "$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/digi_steer.py" \
    -n -1 \
    --inputFiles sim_output.edm4hep.root \
    --outputFile digi_output.edm4hep.root

# --- 4. Reconstruction ---
echo "Running Reconstruction..."
k4run "$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/reco_steer.py" \
    -n -1 \
    --inputFiles digi_output.edm4hep.root \
    --outputFile reco_output.edm4hep.root

# --- Move Outputs ---
FINAL_OUT_DIR=$OUTPUT_DIR/job_${JOB_ID}_${LABEL}
mkdir -p $FINAL_OUT_DIR
echo "Moving files to $FINAL_OUT_DIR"

# Rename files to include Job ID for easier handling later
mv gen_output.hepmc $FINAL_OUT_DIR/gen_output_${JOB_ID}.hepmc
mv sim_output.edm4hep.root $FINAL_OUT_DIR/sim_output_${JOB_ID}.edm4hep.root
mv digi_output.edm4hep.root $FINAL_OUT_DIR/digi_output_${JOB_ID}.edm4hep.root
mv reco_output.edm4hep.root $FINAL_OUT_DIR/reco_output_${JOB_ID}.edm4hep.root

# Cleanup
cd ..
rm -rf $WORKDIR
echo "Job $JOB_ID finished successfully"
