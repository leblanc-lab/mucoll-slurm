#!/bin/bash
# Open an interactive shell in the mucoll-spack v3.1 container on Oscar.
# Usage:  source scripts/shell.sh    (run from an interactive/worker node)

# Use scratch for apptainer temp/cache (the home quota is small).
export APPTAINER_TMPDIR=/oscar/scratch/$USER/apptainer_tmp
export APPTAINER_CACHEDIR=/oscar/scratch/$USER/apptainer_cache
mkdir -p $APPTAINER_TMPDIR
mkdir -p $APPTAINER_CACHEDIR

# Source the shared config to find the local SIF (falls back to docker:// pull).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
source "$SCRIPT_DIR/../config.sh"

if [ -f "$IMAGE" ]; then
    apptainer shell --cleanenv --bind "$DATA_BIND,$WORK_DIR" "$IMAGE"
else
    echo "Local SIF $IMAGE not found; pulling v3.1 from ghcr.io (first run is slow)..."
    apptainer shell --cleanenv docker://ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:v3.1
fi
