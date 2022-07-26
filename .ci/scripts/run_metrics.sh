#!/bin/bash

# run_metrics()
# This script wraps a "docker run" command within metrics_collection_start() and
# metrics_collection_end() function calls.
#
# usage:
#     run_metrics.sh <pge> <run config_fn> (file name only) <data_dir> (full path) <image name>
#     Eg. run_metrics  DSWX_HLS_PGE  dswx_hls.yaml  /Users/..../l30_greenland  opera/proteus:mid_may_2022
#
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

. "${SCRIPT_DIR}"/util.sh

PGE=$1          # pge to run in docker
RUNCONFIG=$2    # runconfig file name (not full path)
DATA_DIR=$3     # data directory for input and output to the docker run command
IMAGE_NAME=$4   # name of the docker image to run stats on, ex: opera_pge/dswx_hls:jehofman-dev
SAMPLE_TIME=$5  # Amount of time between samples (seconds)

# will add the docker tag in a future version
# container_name="${pge_docker_tag}_${PGE}_${RUNCONFIG}"

container_name="$PGE"

metrics_collection_start "$container_name" "$IMAGE_NAME" "$SAMPLE_TIME"

echo "Running pge '{$PGE}' (image $IMAGE_NAME) using run config '$RUNCONFIG'"
echo "Sending 'docker run' command"

#docker run --rm --name "$PGE" -u $UID:$(id -g)\
#  -v "${DATA_DIR}"/runconfig:/home/conda/runconfig:ro \
#  -v "${DATA_DIR}"/input_dir:/home/conda/input_dir:ro \
#  -v "${DATA_DIR}"/output_dir:/home/conda/output_dir \
#  -i --tty opera/proteus:mid_may_2022 sh -ci "python3 proteus-0.1/bin/dswx_hls.py runconfig/dswx_hls.yaml --log output_dir/test_log.log"

docker run --rm --name "${container_name}" -u $UID:$(id -g)\
  -v "${DATA_DIR}"/runconfig:/home/conda/runconfig:ro \
  -v "${DATA_DIR}"/input_dir:/home/conda/input_dir:ro \
  -v "${DATA_DIR}"/output_dir:/home/conda/output_dir \
  -i --tty opera/proteus:mid_may_2022 sh -ci "python3 proteus-0.1/bin/dswx_hls.py runconfig/dswx_hls.yaml --log output_dir/test_log.log"

docker_run_exit_code=$?
echo "Docker run exited with code: " $docker_run_exit_code

metrics_collection_end "$container_name" $docker_run_exit_code "$PGE" "$RUNCONFIG"
