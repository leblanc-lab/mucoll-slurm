#!/bin/bash

podman-hpc run -it --rm -u 0 \
  -v $HOME:$HOME \
  -v $PWD:$PWD \
  -w $PWD \
  ghcr.io/muoncollidersoft/mucoll-sim-ubuntu24:main /bin/bash
