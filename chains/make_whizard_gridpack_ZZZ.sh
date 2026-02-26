#!/bin/bash
#SBATCH --job-name=whizard_gridpack_ZZZ
#SBATCH --output=/oscar/data/mleblan6/mucoll/gridpacks/ZZZ/gridpack.out
#SBATCH --error=/oscar/data/mleblan6/mucoll/gridpacks/ZZZ/gridpack.err
#SBATCH --time=24:00:00
#SBATCH --mem=64G
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64

WORK_DIR=/users/mleblan6/work/bib
GRIDPACK_DIR=/oscar/data/mleblan6/mucoll/gridpacks/ZZZ
SIF=/oscar/data/mleblan6/mucoll/mucoll-sim-ubuntu24:main.sif
SIN_TEMPLATE=$WORK_DIR/mucoll-slurm/whizard/mumu_ZZZ_hadrons_10TeV_gridpack.sin

mkdir -p $GRIDPACK_DIR

echo "Running on host: $(hostname)"
echo "CPUs: $SLURM_CPUS_PER_TASK"
echo "Gridpack output: $GRIDPACK_DIR"

# Substitute the actual gridpack output path into the sin file
# and write it into the gridpack directory so it is self-contained
sed "s|GRIDPACK_OUTPUT_PATH|${GRIDPACK_DIR}|g" $SIN_TEMPLATE > $GRIDPACK_DIR/job.sin

apptainer exec \
    --bind /oscar/data/mleblan6/mucoll,$WORK_DIR \
    $SIF \
    bash -c "
        source /opt/spack/opt/spack/__spack_path_placeholder__/__spack_path_placeholder__/__spack_path_placeholder__/__spack_path_placeholder__/linux-x86_64/mucoll-stack-2026-01-29-gox6efzvyhus5szcxoq3wscjpt5uxvl7/setup.sh
        export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
        cd ${GRIDPACK_DIR}
        whizard job.sin
    "

echo "Gridpack complete. Grid files in $GRIDPACK_DIR:"
ls -lh $GRIDPACK_DIR/*.vg 2>/dev/null || echo "  (no .vg files found at top level — check process subdirectories)"
ls -lh $GRIDPACK_DIR/
