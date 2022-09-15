#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

parse_build_args()
{
  while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      echo "Usage: $(basename $0) [-h|--help] [-s|--sas-image <image name>] [-t|--tag <tag>] [-w|--workspace <path>]"
      exit 0
      ;;
    -s|--sas-image)
      SAS_IMAGE=$2
      shift
      shift
      ;;
    -t|--tag)
      TAG=$2
      shift
      shift
      ;;
    -w|--workspace)
      WORKSPACE=$2
      shift
      shift
      ;;
    -*|--*)
      echo "Unknown arguments $1 $2, ignoring..."
      shift
      shift
      ;;
    *)
      echo "Unknown argument $1, ignoring..."
      shift
      ;;
  esac
  done
}

parse_test_args()
{
  while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      echo "Usage: $(basename $0) [-h|--help] [-t|--tag <tag>] [-w|--workspace <path>]"
      exit 0
      ;;
    -t|--tag)
      TAG=$2
      shift
      shift
      ;;
    -w|--workspace)
      WORKSPACE=$2
      shift
      shift
      ;;
    -*|--*)
      echo "Unknown arguments $1 $2, ignoring..."
      shift
      shift
      ;;
    *)
      echo "Unknown argument $1, ignoring..."
      shift
      ;;
  esac
  done
}

build_script_cleanup() {
  if [[ -z ${KEEP_TEMP_FILES} ]]; then
    echo "Cleaning up staging directory ${STAGING_DIR}..."
    rm -rf ${STAGING_DIR}
  fi
}

copy_pge_files() {
  WORKSPACE=$1
  STAGING_DIR=$2
  PGE_NAME=$3

  cp ${WORKSPACE}/src/opera/__init__.py \
   ${STAGING_DIR}/opera/

  cp ${WORKSPACE}/src/opera/_package.py \
     ${STAGING_DIR}/opera/

  cp ${WORKSPACE}/src/opera/pge/__init__.py \
     ${STAGING_DIR}/opera/pge/

  cp -r ${WORKSPACE}/src/opera/pge/base \
        ${STAGING_DIR}/opera/pge/

  cp -r ${WORKSPACE}/src/opera/pge/${PGE_NAME} \
        ${STAGING_DIR}/opera/pge/

  cp -r ${WORKSPACE}/src/opera/scripts \
        ${STAGING_DIR}/opera/

  cp -r ${WORKSPACE}/src/opera/util \
        ${STAGING_DIR}/opera/

  cp ${WORKSPACE}/COPYING \
     ${STAGING_DIR}/opera

  cp ${WORKSPACE}/requirements.txt \
     ${STAGING_DIR}/opera

  cp ${WORKSPACE}/.flake8 \
     ${STAGING_DIR}/opera

  cp ${WORKSPACE}/.pylintrc \
     ${STAGING_DIR}/opera
}

# Start the metrics collection of both docker stats and the miscellaneous os statistics.
# Parameters:
#     pge:  pge we are working on
#     container_info:  the name of the docker file from which to gather statistics
#     sample_time:  The time between sampling of the statistics.
metrics_collection_start()
{
    local pge=$1
    # Split seconds argument into docker name and tag
    local cont_name="$(echo "$2" | cut -d':' -f1)"
    local container_tag="$(echo "$2" | cut -d':' -f2)"
    # TODO: cont_info should always contain pge_docker_tag, PGE, and runconfig (at a minimum)
    # container_info="${pge}_${cont_name}_${container_tag}"
    local container_info="$pge"

    # If no sample_time value is passed - default to a value of 1
    if [[ -z "$3" ]]
    then
        local sample_time=1
    else
        local sample_time=$3
    fi

    echo "Using sample time of: $sample_time"
    # Initialize output files and statistics format
    metrics_stats="${container_info}_metrics_stats.csv"
    metrics_misc="${container_info}_metrics_misc.csv"

    stat_format="{{.Name}},CPU,{{.CPUPerc}},MEM,{{.MemUsage}},MEM %,{{.MemPerc}},NET,{{.NetIO}},BLOCK,{{.BlockIO}},PIDS,{{.PIDs}}"

    # initialize start seconds and csv file contents - put on first line of each file
    METRICS_START_SECONDS=$SECONDS
    echo "SECONDS,$stat_format" > "$metrics_stats"

    # start the background processes to monitor docker stats
    { while true; do ds=$(docker stats --no-stream --format "${stat_format}" "${pge}" 2>/dev/null); \
    echo "$(metrics_seconds)","$ds" >> "${metrics_stats}"; sleep "$sample_time"; done } & \
    echo "$!" > "${container_info}_metrics_stats_bg_pid.txt"

    # Miscellaneous Statistics

    # test for operating system
    if [[ $OSTYPE == "darwin"* ]]; then
        echo "Mac Operating system: $OSTYPE"
        os="mac"
    else
        echo "Linux Operating system: $OSTYPE"
        os="linux"
    fi

    # Output the column titles
    echo "SECONDS, disk_used, swap_used, total_threads, last_line" > "$metrics_misc"

    # Use 'df' command to capture the amount of space on the '/dev/vda1' file system (-B sets block size (1K)
    # the line represent Filesystem  1K-blocks  Used Blocks Available Blocks %Used Mounted_On
    block_space_cmd='df -B 1024 | grep "/System/Volumes/VM"'

    # Get the number of system threads
    sys_threads_cmd='ps -elf | wc -l'

    if [[ $os == "linux" ]]; then
        # Use 'free' to get the total amount of Swap space available
        swap_space_cmd='free -g | grep Swap'
    else
        swap_space_cmd='echo "N/A"'
    fi

    # Set directory fo the log file
    last_log_line_dir='pwd'

    lll_file="last_log_line.txt"
    find ${last_log_line_dir} -name ${lll_file} -exec rm {} \; 2>/dev/null
    lll_cmd="echo $(find ${last_log_line_dir} -name ${lll_file} -exec rm {} \; 2>/dev/null)"

    { while true; do dus=$(eval "$block_space_cmd"); swu=$(eval "$swap_space_cmd"); ths=$(eval "$sys_threads_cmd"); \
    lll=$(eval "$lll_cmd"); echo "$(metrics_seconds), $dus, $swu, $ths, $lll" >> "${metrics_misc}"; \
    sleep "$sample_time"; done } & \
    echo "$!" >> "${container_info}_metrics_misc_bg_pid.txt"
}

# End the metrics collection of both docker stats and the miscellaneous os statistics.
# Parameters:
#     container_info: basic container information (TODO: right now this is incomplete)
#     exit_code:  Exit code from Docker run (0 = success, non-zero = failure).
metrics_collection_end()
{
    local container_info=$1
    local exit_code=$2
    # TODO The variables below will be used in the future.
    # mce_pge=$3
    # mce_runconfig=$4

    local metrics_stats="${container_info}_metrics_stats.csv"
    local metrics_misc="${container_info}_metrics_misc.csv"

    # kill the background tasks (the pid number is stored in the file below)
    kill "$(cat "${container_info}_metrics_stats_bg_pid.txt")"
    rm "${container_info}"_metrics_stats_bg_pid.txt
    kill "$(cat "${container_info}_metrics_misc_bg_pid.txt")"
    rm "${container_info}"_metrics_misc_bg_pid.txt

    if [[ $exit_code == 0 ]]
    then
        python3 "$SCRIPT_DIR"/process_metric_data.py "$container_info" "$metrics_stats" "$metrics_misc"
        process_metrics_exit_code=$?
        if [[ $process_metrics_exit_code == 0 ]]
        then
            echo "Remove temporary gathering files."
            rm "$metrics_stats"
            rm "$metrics_misc"
        fi
    else
        echo "Docker exited with an error and so metrics will not be processed or uploaded (csv files will be saved)."git
    fi

    echo "metrics_collection has completed."
}

metrics_seconds()
{
    echo $(( SECONDS - METRICS_START_SECONDS ))
}
