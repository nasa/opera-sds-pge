#!/bin/bash

# run_metrics()
#
# This script wraps a "docker run" command with metrics_collection_start() and
# metrics_collection_end() function calls.
#
# usage:
#     run_metrics.sh <pge> <run config_fn> (file name only) <data_dir> (full path) <image name>
#
# example: NOT IMPLEMENTED
#     run_metrics.sh l1b_hr_slc l1bhrslc.rc.xml 64 32 16 8 4 2 1bash
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

. "${SCRIPT_DIR}"/util.sh

PGE=$1          # pge to run in docker
RUNCONFIG=$2    # runconfig file name (not full path)
DATA_DIR=$3     # data directory for input and output to the docker run command
IMAGE_NAME=$4   # name of the docker image to run stats on, ex: opera_pge/dswx_hls:jehofman-dev

# will add the docker tag in a future version
# container_name="${pge_docker_tag}.${PGE}.${RUNCONFIG}"

container_name="$PGE"

metrics_collection_start "$container_name"

echo "Running pge '$PGE' (image $IMAGE_NAME) using run config '$RUNCONFIG'"
echo "Sending 'docker run' command"

docker run --rm --name "${container_name}" -u $UID:$(id -g)\
  -v ${DATA_DIR}/runconfig:/home/conda/runconfig:ro \
  -v ${DATA_DIR}/input_dir:/home/conda/input_dir:ro \
  -v ${DATA_DIR}/output_dir:/home/conda/output_dir \
  -i --tty ${IMAGE_NAME} \
  --file /home/conda/runconfig/${RUNCONFIG}

docker_run_exit_code=$?
echo "Docker run exited with code $docker_run_exit_code"

metrics_collection_end "$container_name" $docker_run_exit_code "$PGE" "$RUNCONFIG"
