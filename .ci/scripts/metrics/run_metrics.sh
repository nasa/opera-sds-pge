#!/bin/bash

# run_metrics()
# This script wraps a "docker run" command within metrics_collection_start() and
# metrics_collection_end() function calls.  It is to test the calls on local machines.
#
# usage:
#     run_metrics.sh <pge_name> <runconfig> <data_dir> <container home> <image name> <image tag> <sample time>
#     Eg. bash run_metrics.sh  DSWX_HLS_PGE  dswx_hls.yaml  /Users/..../test_datasets  /home/conda  opera/proteus cal_val_3.1 5
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/../util/test_int_util.sh
. "$SCRIPT_DIR"/../util/util.sh

# TODO: validate number of provided arguments matches expected,
#       and print help usage (or set defaults) if wrong
PGE_NAME=$1        # PGE name
RUNCONFIG=$2       # Runconfig file path
DATA_DIR=$3        # Directory to get input and write output from PGE
CONTAINER_HOME=$4  # The path of the home directory is within the container
PGE_IMAGE=$5       # Name of the docker image to run stats on
PGE_TAG=$6         # Name of the docker tag
SAMPLE_TIME=$7     # Amount of time between samples (seconds)

container_name="${PGE_NAME}-${PGE_IMAGE}"

# Create the test output directory in the workspace
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath "$(dirname "$(realpath "$0")")"/../..)
test_int_setup_results_directory

# Start metrics collection
metrics_collection_start "$PGE_NAME" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

echo "Running pge '$PGE_NAME' (image $PGE_IMAGE, tag $PGE_TAG) using run config '$RUNCONFIG'"
echo "Sending 'docker run' command"

FULL_IMAGE_NAME="${PGE_IMAGE}:${PGE_TAG}"
RUNCONFIG_FILENAME=$(basename -- "$RUNCONFIG")

docker run --rm -w "${CONTAINER_HOME}" -u $UID:$(id -g) --name="${container_name}" \
  -v "${DATA_DIR}"/runconfig:"${CONTAINER_HOME}"/runconfig:ro \
  -v "${DATA_DIR}"/input_dir:"${CONTAINER_HOME}"/input_dir:ro \
  -v "${DATA_DIR}"/output_dir:"${CONTAINER_HOME}"/output_dir \
  -i --tty "${FULL_IMAGE_NAME}" --file "${CONTAINER_HOME}/${RUNCONFIG_FILENAME}"

docker_run_exit_code=$?
echo "Docker run exited with code: " $docker_run_exit_code

metrics_collection_end "$PGE_NAME" "$container_name" "$docker_run_exit_code" "$TEST_RESULTS_DIR"
