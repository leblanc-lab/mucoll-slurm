#!/bin/bash
# =============================================================================
#  mucoll-slurm : single configuration file
# =============================================================================
#  This is the main file you should normally need to edit.
#  It is sourced both on the login node (by the Python submit scripts) and
#  inside the container (by the chain scripts), so stick to just `export`s.
#
#  Quick start:
#    1. Make sure your output area exists:  the scripts create it for you under
#       OUTPUT_BASE_DIR below, but you need write access to DATA_GROUP_DIR.
#    2. (One time) pull the v3.1 image to a shared SIF -- see README.md.
#    3. Run:  python submit_pgun.py        (particle gun, no BIB)
#       or flip BIB=True inside submit_pgun.py for "with BIB".
# =============================================================================

# --- Repository layout (auto-detected) ---------------------------------------
# WORK_DIR = the directory that contains both mucoll-slurm/ and mucoll-benchmarks/.
# Derived from this file's own location so the checkout can live anywhere.
WORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
export WORK_DIR
export MUCOLL_BENCHMARKS_PATH="$WORK_DIR/mucoll-benchmarks"

# --- Shared group storage on Oscar -------------------------------------------
# All members of the ccv-mleblan6 allocation share this directory; each user
# writes to their own $USER subdirectory inside it.
export DATA_GROUP_DIR="/oscar/data/mleblan6/mucoll"

# --- Container image (mucoll-spack v3.1, sim layer, ubuntu24) -----------------
# One-time pull (see README.md):
#   apptainer pull "$DATA_GROUP_DIR/mucoll-sim-ubuntu24:v3.1.sif" \
#       docker://ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:v3.1
export IMAGE="$DATA_GROUP_DIR/mucoll-sim-ubuntu24:v3.1.sif"

# Image used for the Whizard *signal* chains (submit_whizard.py, make_gridpack.py).
# The v3.1 sim image includes the event-generator layer, including Whizard.
export WHIZARD_IMAGE="$DATA_GROUP_DIR/mucoll-sim-ubuntu24:v3.1.sif"

# --- Detector geometry -------------------------------------------------------
export GEOM_NAME="MAIA_v0"

# --- Output ------------------------------------------------------------------
# Per-user output area inside the shared group directory.
export OUTPUT_BASE_DIR="$DATA_GROUP_DIR/$USER/output"

# --- Apptainer bind mounts ---------------------------------------------------
# Bind the shared group dir (image + BIB + output) and the code checkout.
export DATA_BIND="$DATA_GROUP_DIR"

# --- Beam-Induced Background (BIB) overlay samples ---------------------------
# Used only when a job is launched "with BIB". Each path is a DIRECTORY of
# *.edm4hep.root files (trailing slash matters); the overlay enumerates them.
export BIB_DIR="$DATA_GROUP_DIR/bib/Feb12/10TeV_MAIA_edm4hep"
export BIB_MUPLUS="$BIB_DIR/MUPLUS/"
export BIB_MUMINUS="$BIB_DIR/MUMINUS/"
# Number of BIB files overlaid per signal event (per polarity). 812 = the digi
# default (assumes 45 phi clones). Tune per study; the README example uses 60.
export BIB_NUMBER=812
