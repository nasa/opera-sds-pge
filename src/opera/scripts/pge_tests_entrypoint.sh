#!/usr/bin/env bash
# Main docker entrypoint for testing of OPERA PGE docker containers

DOCKER_ENTRYPOINT_SCRIPT_DIR=$(dirname ${BASH_SOURCE[0]})
PGE_PROGRAM_DIR=/home/conda

# Python path setup
export PYTHONPATH=$PYTHONPATH:${PGE_PROGRAM_DIR}

# Run whatever the caller wants.
# This could be something like a utility call to pylint/flake8, or an invocation
# of pytest on the opera_pge unit test suite

"$@"
