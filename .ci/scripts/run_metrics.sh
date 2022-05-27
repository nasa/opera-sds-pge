#!/bin/bash

# run_metrics()
#
# This script wraps a "docker run" command with metrics_collection_start() and
# metrics_collection_end() function calls.
#
# usage:
#     run_metrics_series.sh <pge> <run config_fn> (file name only) <data_dir> (full path)
#
# example: NOT IMPLEMENTED
#     run_metrics_series.sh l1b_hr_slc l1bhrslc.rc.xml 64 32 16 8 4 2 1bash
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

. "${SCRIPT_DIR}"/util.sh

PGE=$1          # pge to run in docker
RUNCONFIG=$2    # runconfig file name (not full path)
DATA_DIR=$3     # data directory for input and output to the docker run command

# will add the docker tag in a future version
# container_name="${pge_docker_tag}.${PGE}.${RUNCONFIG}"

container_name="$PGE"

metrics_collection_start "$container_name"

echo "Running pge '$PGE' using run config '$RUNCONFIG'"
echo "Sending 'docker run' command"

# Set variables to use in 'docker run' command
data_set_dir=$DATA_DIR
image_name="opera_pge/dswx_hls:jehofman-dev"

docker run --rm --name "${container_name}" -u $UID:$(id -g)\
  -v ${data_set_dir}/runconfig:/home/conda/runconfig:ro \
  -v ${data_set_dir}/input_dir:/home/conda/input_dir:ro \
  -v ${data_set_dir}/output_dir:/home/conda/output_dir \
  -i --tty ${image_name} \
  --file /home/conda/runconfig/${RUNCONFIG}

docker_run_exit_code=$?
echo "Docker run exited with code $docker_run_exit_code"

metrics_collection_end "$container_name" $docker_run_exit_code "$PGE" "$RUNCONFIG"
