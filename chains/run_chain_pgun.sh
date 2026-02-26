#!/bin/bash
set -e

# Arguments
JOB_ID=$1
NEVENTS=$2
OUTPUT_DIR=$3
MUCOLL_BENCHMARKS_PATH=$4
PDG=${5:-11}
PT=${6:-100}
THETA_MIN=${7:-10}
THETA_MAX=${8:-170}

echo "Starting job $JOB_ID with $NEVENTS events"
echo "Output directory: $OUTPUT_DIR"
echo "Benchmarks path: $MUCOLL_BENCHMARKS_PATH"
echo "Particle: PDG=$PDG, pT=$PT GeV, Theta=[$THETA_MIN, $THETA_MAX]"

# Source the main environment setup inside the container. This is the one that was moved from mucoll-slurm/ when setting up the work directory.
source $MUCOLL_BENCHMARKS_PATH/../setup.sh

# Setup detector geometry and PYTHONPATH for digi/reco steering files.
# Source setup_digireco.sh from its location, passing the benchmarks path directly
# so it can resolve absolute paths correctly regardless of cwd.
source $MUCOLL_BENCHMARKS_PATH/k4MuCPlayground/setup_digireco.sh $MUCOLL_BENCHMARKS_PATH MAIA_v0

# Create a temporary working directory
WORKDIR=/tmp/mucoll_job_${JOB_ID}_${RANDOM}
mkdir -p $WORKDIR
cd $WORKDIR
echo "Working in $WORKDIR"

# Copy PandoraSettings needed for reconstruction
cp -r $MUCOLL_BENCHMARKS_PATH/reconstruction/PandoraSettings/ ./

# --- 1. Generation ---
echo "Running Generation..."
python $MUCOLL_BENCHMARKS_PATH/generation/pgun/pgun_edm4hep.py \
    -p 1 -e $NEVENTS --pdg $PDG --pt $PT --theta $THETA_MIN $THETA_MAX -- gen_output.edm4hep.root

# --- 2. Simulation ---
echo "Running Simulation..."
ddsim --steeringFile $MUCOLL_BENCHMARKS_PATH/simulation/steer_baseline.py \
    --numberOfEvents $NEVENTS \
    --inputFiles gen_output.edm4hep.root \
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
FINAL_OUT_DIR=$OUTPUT_DIR/job_${JOB_ID}
mkdir -p $FINAL_OUT_DIR
echo "Moving files to $FINAL_OUT_DIR"

# Rename files to include Job ID for easier handling later
mv gen_output.edm4hep.root $FINAL_OUT_DIR/gen_output_${JOB_ID}.edm4hep.root
mv sim_output.edm4hep.root $FINAL_OUT_DIR/sim_output_${JOB_ID}.edm4hep.root
mv digi_output.edm4hep.root $FINAL_OUT_DIR/digi_output_${JOB_ID}.edm4hep.root
mv reco_output.edm4hep.root $FINAL_OUT_DIR/reco_output_${JOB_ID}.edm4hep.root

# Cleanup
cd ..
rm -rf $WORKDIR
echo "Job $JOB_ID finished successfully"
