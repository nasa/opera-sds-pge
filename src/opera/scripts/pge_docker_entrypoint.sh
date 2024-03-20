#!/usr/bin/env bash

# Docker entrypoint script for OPERA PGE docker containers
# Responsible for configuring the shell environment for the execution of pge_main.py

DOCKER_ENTRYPOINT_SCRIPT_DIR=$(dirname ${BASH_SOURCE[0]})
PGE_PROGRAM_DIR=${PGE_DEST_DIR}

# Python path setup
export PYTHONPATH=$PYTHONPATH:${PGE_PROGRAM_DIR}

# Run the PGE wrapped by the following:
# The "PGE main" script, which is part of the opera_pge repo copied into the
# SAS container

${PGE_PROGRAM_DIR}/opera/scripts/pge_main.py "$@"
