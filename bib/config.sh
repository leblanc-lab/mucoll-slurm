#!/bin/bash
# ============================================================================
# BIB Production Workflow (v3.1 image, Perlmutter) — Central Configuration
# ============================================================================
# FLUKA -> GEN -> SIM -> DIGI -> RECO produced as FOUR separate sets of batch
# jobs, each driven by PyTaskFarmer (N workers/node consuming a shared task
# list). Sourced by test_chain_single.sh and parsed by submit_bib.py.
#
# This is the Perlmutter/Shifter port of the old ~/bib toolkit, adapted to the
# v3.1 container and the current mucoll-benchmarks steering conventions.
# ============================================================================

# ----- Input / Output -----
# Directory containing FLUKA binary files (summary*_DET_IP.dat)
FLUKA_INPUT_DIR="/global/cfs/cdirs/m5197/data/bib/10TeV-2024/Fluka/joined_data"

# Base output directory. Subfolders GEN/ SIM/ DIGI/ RECO/ logs/ are created
# automatically, each with MUPLUS/ and MUMINUS/ beam subdirectories.
OUTPUT_BASE="/global/cfs/cdirs/m5197/mleblanc/MuonCollider/data/bib-v3p1-fmt2-norm1"

# ----- Software Paths -----
# Path to the mucoll-benchmarks checkout (the current benchmark working dir).
# NERSC Shifter auto-mounts $HOME at the same absolute path inside the
# container, so the real host path works directly.
MUCOLL_BENCHMARKS="${BIB_ROOT:-/global/homes/m/mleblanc/benchmark}/mucoll-benchmarks"

# Container image (Shifter docker ref; pull once with `shifterimg pull <ref>`).
CONTAINER_IMAGE="ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:v3.1"

# Detector geometry name (MAIA_v0, MuSIC_v0, MuColl_v1, ...)
DETECTOR_GEOM="MAIA_v0"

# ----- SLURM (NERSC Perlmutter) -----
SLURM_ACCOUNT="m5197"
SLURM_CONSTRAINT="cpu"
SLURM_QOS_PROD="regular"
SLURM_QOS_TEST="debug"

# ----- PyTaskFarmer -----
# Path to pytaskfarmer.py (must be visible on compute nodes via shared FS).
PYTASKFARMER="${BIB_ROOT:-/global/homes/m/mleblanc/benchmark}/pytaskfarmer/pytaskfarmer.py"

# Number of full Perlmutter CPU nodes per step.
GEN_NODES=1
SIM_NODES=1
DIGI_NODES=1
RECO_NODES=1

# Workers per node (Python processes PTF spawns). A Perlmutter CPU node has
# 128 physical cores. RECO is memory-hungry, so use fewer workers w/ ACTS threads.
GEN_WORKERS=128
SIM_WORKERS=128
DIGI_WORKERS=128
RECO_WORKERS=32

# ACTS / Gaudi-Hive threads per worker (passed to k4run as --numThreads).
# 1 = serial event loop. RECO uses 4 so 32 workers × 4 = 128 threads/node
# with much lower memory pressure than 128 independent single-thread workers.
DIGI_THREADS=1
RECO_THREADS=4

# ----- GEN step options (fluka_to_edm4hep.py) -----
GEN_BX_TIME="0.0"
GEN_NORMALIZATION="1.0"
# Set to a value to apply cuts, or leave empty for no cut
GEN_T_MAX=""
GEN_NE_MIN=""

# ----- Per-step wall-time requests -----
GEN_TIME="02:00:00"
SIM_TIME="04:00:00"
DIGI_TIME="03:00:00"
RECO_TIME="06:00:00"
