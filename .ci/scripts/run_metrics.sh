#!/bin/bash

# run_metrics()
# {
# Run a PGE from the test data directory (where the runconfig XML is) with different ProcessingThreads values
#
# This script wraps a "docker run" command with metrics_collection_start() and
# metrics_collection_end() function calls.  See swot_pge/.ci/util.sh for details.
#
# usage:
#     run_metrics_series.sh <pge> <run config> <processing threads list, e.g. 8 16 32 48 96>
#
# example:
#     run_metrics_series.sh l1b_hr_slc l1bhrslc.rc.xml 64 32 16 8 4 2 1bash
#
# If there is a ProcessingThreads entry in the run config, it will be adjusted for each loop iteration.
# If there is not a ProcessingThreads, then the sed command will not modify the run config.

echo "hello"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

. "${SCRIPT_DIR}"/util.sh

PGE=$1   # pge
RC=$2    # runconfig file
# shift 2

# Temporary runconfig
RC="/home/conda/runconfig/dswx_hls_sample_runconfig-v1.0.0-er.4.1.yaml"

echo "$PGE"
echo "$RC"

# container_name="${ghrVersion}.${PGE}.${RC}"

container_name="$PGE"
#
metrics_collection_start "$container_name"
#
echo "Running pge $PGE using run config $RC"
#
# docker run --rm --name "${container_name}" -u ${UID} -v "$(pwd)":/pge/run -w /pge/run pge/"${PGE}":"${ghrVersion}" /pge/run/"${RC}"
echo "Starting docker"
docker run --rm --name "${container_name}" -u $UID:$(id -g)\
  -v /Users/jehofman/Documents/OPERA/docker_latest/DSWX/delivery_2.1_mid_may/l30_greenland/runconfig:/home/conda/runconfig:ro \
  -v /Users/jehofman/Documents/OPERA/docker_latest/DSWX/delivery_2.1_mid_may/l30_greenland/input_dir:/home/conda/input_dir:ro \
  -v /Users/jehofman/Documents/OPERA/docker_latest/DSWX/delivery_2.1_mid_may/l30_greenland/output_dir:/home/conda/output_dir \
  -i --tty opera_pge/dswx_hls:jehofman-dev \
   --file /home/conda/runconfig/dswx_hls_sample_runconfig-v1.0.0-er.4.1.yaml
   #  --file ${RC}
#
docker_run_exit_code=$?
echo "docker run exited with code $docker_run_exit_code"
#
metrics_collection_end "$container_name" $docker_run_exit_code "$PGE" "$RC"

# }
