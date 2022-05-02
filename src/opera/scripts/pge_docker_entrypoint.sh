#!/usr/bin/env bash

# Docker entrypoint script for OPERA PGE docker containers
# Responsible for configuring the shell environment for the execution of pge_main.py

DOCKER_ENTRYPOINT_SCRIPT_DIR=$(dirname ${BASH_SOURCE[0]})
PGE_PROGRAM_DIR=/home/conda

# Python path setup
export PYTHONPATH=$PYTHONPATH:${PGE_PROGRAM_DIR}

# Run the PGE wrapped by the following:
# 1) docker-stats-on-exit-shim to collect computer usage info.
#    https://github.com/delcypher/docker-stats-on-exit-shim
# 2) The "PGE main" script, which is part of the opera_pge repo copied into the
#    SAS container

${DOCKER_ENTRYPOINT_SCRIPT_DIR}/pge_run_docker_stats.sh \
${PGE_PROGRAM_DIR}/opera/scripts/pge_main.py "$@"
