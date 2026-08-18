#!/bin/bash
set -e

# Arguments
JOB_ID=$1
NEVENTS=$2
OUTPUT_DIR=$3
MUCOLL_BENCHMARKS_PATH=$4
GRIDPACK_DIR=${5:-""}

echo "Starting job $JOB_ID with $NEVENTS events"
echo "Output directory: $OUTPUT_DIR"
echo "Benchmarks path: $MUCOLL_BENCHMARKS_PATH"
if [ -n "$GRIDPACK_DIR" ]; then
    echo "Using Whizard gridpack from: $GRIDPACK_DIR"
else
    echo "No gridpack provided: running full phase-space integration (slow)"
fi

# Load shared config + spack environment (glob-based, image-version agnostic).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
source "$SCRIPT_DIR/../config.sh"
source "$SCRIPT_DIR/../scripts/setup.sh"

# Setup detector geometry and PYTHONPATH for digi/reco steering files.
source "$MUCOLL_BENCHMARKS_PATH/setup_config.sh" "$MUCOLL_BENCHMARKS_PATH" "$GEOM_NAME"

# Whizard is provided by the v3.1 sim image's generator layer.
if ! command -v whizard >/dev/null 2>&1; then
    echo "ERROR: 'whizard' not found in this image. Signal production needs a" >&2
    echo "       Whizard-capable image -- set WHIZARD_IMAGE in config.sh." >&2
    exit 1
fi

# Create a temporary working directory
WORKDIR=/tmp/mucoll_job_${JOB_ID}_${RANDOM}
mkdir -p $WORKDIR
cd $WORKDIR
echo "Working in $WORKDIR"

# Whizard runtime libs (found by glob so it survives image updates).
WHIZARD_LIB=$(ls -d /opt/spack/opt/spack/*/*/*/*/linux-x86_64/whizard-*/lib 2>/dev/null | sort | tail -n1)
[ -n "$WHIZARD_LIB" ] && export LD_LIBRARY_PATH="$WHIZARD_LIB:$LD_LIBRARY_PATH"

# Copy PandoraSettings needed for reconstruction
cp -r "$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/PandoraSettings/" ./

# --- 1. Generation (Whizard) ---
echo "Running Generation..."
# Copy the steering file (kept in this repo) and update the number of events
cp "$SCRIPT_DIR/../whizard/mumu_ZZZ_hadrons_10TeV.sin" ./job.sin
# Update seed and n_events for both processes
sed -i "s/seed = .*/seed = $((1234 + JOB_ID))/" job.sin
sed -i "s/n_events = .*/n_events = $NEVENTS/" job.sin

# If a gridpack directory is provided, copy pre-computed VAMP grids locally.
if [ -n "$GRIDPACK_DIR" ]; then
    mkdir -p ./grids
    cp "$GRIDPACK_DIR/grid_mumu_ZZZ_hadrons"/* ./grids/
    sed -i "/^integrate (zz_to_hadrons)/i ?rebuild_grids = false\n\$integrate_workspace = \"grids\"" job.sin
fi

whizard job.sin

# We have output: mumu_zz_hadrons_10TeV.hepmc
mv mumu_zz_hadrons_10TeV.hepmc gen_output.hepmc

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
    --inputFiles sim_output.edm4hep.root \
    --outputFile digi_output.edm4hep.root

# --- 4. Reconstruction ---
echo "Running Reconstruction..."
k4run "$MUCOLL_CONFIG/$MUCOLL_CONFIG_NAME/reco_steer.py" \
    --inputFiles digi_output.edm4hep.root \
    --outputFile reco_output.edm4hep.root

# --- Move Outputs ---
FINAL_OUT_DIR=$OUTPUT_DIR/job_${JOB_ID}_ZZ
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
