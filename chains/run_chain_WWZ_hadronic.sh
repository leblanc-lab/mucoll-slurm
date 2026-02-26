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
    echo "No gridpack provided: running phase-space integration"
fi

source /opt/spack/opt/spack/__spack_path_placeholder__/__spack_path_placeholder__/__spack_path_placeholder__/__spack_path_placeholder__/linux-x86_64/mucoll-stack-2026-01-29-gox6efzvyhus5szcxoq3wscjpt5uxvl7/setup.sh

# Setup detector geometry and PYTHONPATH for digi/reco steering files.
# Source setup_digireco.sh from its location, passing the benchmarks path directly
# so it can resolve absolute paths correctly regardless of cwd.
source $MUCOLL_BENCHMARKS_PATH/k4MuCPlayground/setup_digireco.sh $MUCOLL_BENCHMARKS_PATH MAIA_v0

# Create a temporary working directory
WORKDIR=/tmp/mucoll_job_${JOB_ID}_${RANDOM}
mkdir -p $WORKDIR
cd $WORKDIR
echo "Working in $WORKDIR"

# This path depends on the image. If the image is updated, this will need to change.
export LD_LIBRARY_PATH=/opt/spack/opt/spack/__spack_path_placeholder__/__spack_path_placeholder__/__spack_path_placeholder__/__spack_path_placeholder__/linux-x86_64/whizard-3.1.5-2wpmahrsf5vaircj7tmf5hdo5fwz2hhw/lib:$LD_LIBRARY_PATH

# Copy PandoraSettings needed for reconstruction
cp -r $MUCOLL_BENCHMARKS_PATH/reconstruction/PandoraSettings/ ./

# --- 1. Generation (Whizard) ---
echo "Running Generation..."
# Copy the steering file and update the number of events
cp $MUCOLL_BENCHMARKS_PATH/generation/signal/whizard/mumu_WWZ_hadrons_10TeV.sin ./job.sin
# Update seed and n_events for both processes
sed -i "s/seed = .*/seed = $((1234 + JOB_ID))/" job.sin
sed -i "s/n_events = .*/n_events = $NEVENTS/" job.sin

# If a gridpack directory is provided, copy pre-computed VAMP grids locally.
if [ -n "$GRIDPACK_DIR" ]; then
    mkdir -p ./grids
    cp "$GRIDPACK_DIR/grid_mumu_WWZ_hadrons"/* ./grids/
    sed -i "/^integrate (ww_to_hadrons)/i ?rebuild_grids = false\n\$integrate_workspace = \"grids\"" job.sin
fi

whizard job.sin

# We have output: mumu_ww_hadrons_10TeV.hepmc
mv mumu_ww_hadrons_10TeV.hepmc gen_output.hepmc

# --- 2. Simulation ---
echo "Running Simulation..."
# ddsim can read hepmc directly.
ddsim --steeringFile $MUCOLL_BENCHMARKS_PATH/simulation/steer_baseline.py \
    --numberOfEvents $NEVENTS \
    --inputFiles gen_output.hepmc \
    --outputFile sim_output.edm4hep.root

# --- 3. Digitization ---
echo "Running Digitization..."
k4run $MUCOLL_BENCHMARKS_PATH/digitization/digi_steer.py \
    --IOSvc.Input sim_output.edm4hep.root \
    --IOSvc.Output digi_output.edm4hep.root

# --- 4. Reconstruction ---
echo "Running Reconstruction..."
k4run $MUCOLL_BENCHMARKS_PATH/reconstruction/reco_steer.py \
    --IOSvc.Input digi_output.edm4hep.root \
    --IOSvc.Output reco_output.edm4hep.root

# --- Move Outputs ---
FINAL_OUT_DIR=$OUTPUT_DIR/job_${JOB_ID}_WW
mkdir -p $FINAL_OUT_DIR
echo "Moving files to $FINAL_OUT_DIR"

ls -lh

# Rename files to include Job ID for easier handling later
mv gen_output.hepmc $FINAL_OUT_DIR/gen_output_${JOB_ID}.hepmc
mv sim_output.edm4hep.root $FINAL_OUT_DIR/sim_output_${JOB_ID}.edm4hep.root
mv digi_output.edm4hep.root $FINAL_OUT_DIR/digi_output_${JOB_ID}.edm4hep.root
mv reco_output.edm4hep.root $FINAL_OUT_DIR/reco_output_${JOB_ID}.edm4hep.root

ls -lh $FINAL_OUT_DIR

# Cleanup
cd ..
rm -rf $WORKDIR
echo "Job $JOB_ID finished successfully"
