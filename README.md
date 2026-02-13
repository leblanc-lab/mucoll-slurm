## Setup

### OSCAR

Let's set up a workspace to get started, then check out this repository:

```
cd work/
mkdir bib
cd bib/
git@github.com:leblanc-lab/mucoll-slurm.git
cp mucoll-slurm/scripts/* .
```

On OSCAR, the first thing you're going to want to do is to enter a worker node to do the setup. You can run the `interact.sh` script, which does the following:

```
interact -n 64 -m 32g -t 8:00:00
```

This will give you 64 CPUs and 32g of RAM for 8 hours. You likely *do not* need this many resources for day-to-day running, but it is helpful when setting up the apptainer shell for the first time. Edit the script accordingly to decrease the number of cores you request in the future.

You'll need to check out the mucoll-benchmarks repository, and checkout the k4MuC branch:

```
git clone git@github.com:samf25/mucoll-benchmarks.git && cd mucoll-benchmarks/ && git checkout k4MuC && cd ../
```

You'll need to download and unpack the µC apptainer image. This can take a minute and requires some space, so you may want to use a scratch disk to do so:

```
# Set the temporary directory to your scratch space: adjust as appropriate for your system
export APPTAINER_TMPDIR=/oscar/scratch/$USER/apptainer_tmp
export APPTAINER_CACHEDIR=/oscar/scratch/$USER/apptainer_cache

# Create these directories if they don't exist
mkdir -p $APPTAINER_TMPDIR
mkdir -p $APPTAINER_CACHEDIR

# This one can take a while ...
apptainer shell --cleanenv docker://ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:main
```

Once you're in the image, run the setup script:

```
source /opt/spack/opt/spack/__spack_path_placeholder__/__spack_path_placeholder__/__spack_path_placeholder__/__spack_path_placeholder__/linux-x86_64/mucoll-stack-2026-01-29-gox6efzvyhus5szcxoq3wscjpt5uxvl7/setup.sh

# Optional: I like to run the following to have my prompt and terminal colours again
# export PS1="[\u@\h \w]\$ "
# alias ls='ls --color=auto'
```

### NERSC (Ignore on OSCAR)

At NERSC, you don't have apptainer and so need to use podman instead. This is why there is a separate `shell_nersc.sh` script:

```
#!/bin/bash

podman-hpc run -it --rm -u 0 \
  -v $HOME:$HOME \
  -v $PWD:$PWD \
  -w $PWD \
  ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:main /bin/bash
```

## Running GEN/SIM/DIGI/RECO

To recap the above: in subsequent shells, you should always do the following to get set up for running by
  * Entering a worker node, no one wants you to run production tests on the login node.
  * Entering the apptainer image
  * Running the setup script inside of the apptainer image

```
source interact.sh
source shell.sh
source setup.sh
```

I have provided these instructions to be run *from the bib directory we made above*, and so they differ from the instructions in `mucoll-playground`.

To run GEN/SIM/DIGI/RECO, first we need to set the detector geometry to either MAIA or MUSIC:

```
cp -r mucoll-benchmarks/reconstruction/PandoraSettings/ ./
source mucoll-benchmarks/k4MuCPlayground/setup_digireco.sh ./ MAIA_v0

# you should see the following output
   ╭──────────────────────────────────────────────╮
   │      Setting All Environment Variables:      │
   │             MUCOLL_GEO from k4geo            │
   │          Others from k4actstracking          │
   ├──────────────────────────────────────────────┤
   │   MUCOLL_GEOM_NAME = MAIA_v0                 │
   │   MUCOLL_GEO       = MAIA_v0.xml             │
   │   MUCOLL_TGEO      = MAIA_v0.root            │
   │   MUCOLL_MATMAP    = MAIA_v0_material.json   │
   │   MUCOLL_TGEO_DESC = MAIA_v0.json            │
   ╰──────────────────────────────────────────────╯
```

To run GEN/SIM/DIGI/RECO for a particle gun event, you can do e.g.:

### GEN

```
python mucoll-benchmarks/generation/pgun/pgun_edm4hep.py \
    -p 1 -e 1 --pdg 11 --pt 100 --theta 10 170 -- gen_output.edm4hep.root
```

### SIM

```
ddsim --steeringFile mucoll-benchmarks/simulation/steer_baseline.py --numberOfEvents 1
```

### DIGI

```
k4run mucoll-benchmarks/digitization/digi_steer.py
```

### RECO

```
k4run mucoll-benchmarks/reconstruction/reco_steer.py
```

If you made it through these commands, you should have some output to analyse! Try to open it up, make a plot, and then try running more events with the particle gun.


## Batch scripts

There are scripts to submit jobs at production scale in `mucoll-slurm/`. Please handle these with care, and don't try running them until you've successfully tested the workflow above. Instructions for how to use those scripts are found in the `README_BATCH.md` file.


## Instructions for generating BIB events from FLUKA inputs

Coming later ...

`mucoll-benchmarks/generation/bib/fluka_to_edm4hep.py`
