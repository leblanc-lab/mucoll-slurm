#!/bin/bash

# Set the temporary directory to your scratch space (where you have plenty of space)
export APPTAINER_TMPDIR=/oscar/scratch/$USER/apptainer_tmp
export APPTAINER_CACHEDIR=/oscar/scratch/$USER/apptainer_cache

# Create these directories if they don't exist
mkdir -p $APPTAINER_TMPDIR
mkdir -p $APPTAINER_CACHEDIR

#apptainer shell --cleanenv docker://ghcr.io/muoncollidersoft/mucoll-sim-alma9:master
apptainer shell --cleanenv docker://ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:main
