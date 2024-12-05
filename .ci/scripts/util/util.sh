#!/bin/bash

parse_args()
{
  if [ $# -eq 1 ]; then 
     if [ $1 == "--help" ] || [ $1 == "-h" ]; then
	echo "Usage: $(basename $0) PGE_NAME RUNCONFIG DATA_DIR CONTAINER_HOME PGE_IMAGE PGE_TAG SAMPLE_TIME"
       	exit 0
     else
	echo "$1 is too few arguments"	
	exit 0
     fi
   fi
   if [ $# -lt 7 ]; then
	echo "Too few arguments - require 7"
	echo "Usage: $(basename $0) PGE_NAME RUNCONFIG DATA_DIR CONTAINER_HOME PGE_IMAGE PGE_TAG SAMPLE_TIME"
        exit 0
   fi
}

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
  echo "Copying PGE files."
  mkdir -p ${STAGING_DIR}/opera/pge
  mkdir -p ${STAGING_DIR}/opera/.ci/scripts

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

  cp -rL ${WORKSPACE}/.ci/scripts/${PGE_NAME} \
        ${STAGING_DIR}/opera/.ci/scripts/

  cp -r  ${WORKSPACE}/.ci/scripts/metrics \
        ${STAGING_DIR}/opera/.ci/scripts/

  cp -r ${WORKSPACE}/.ci/scripts/util \
        ${STAGING_DIR}/opera/.ci/scripts/

  cp ${WORKSPACE}/COPYING \
     ${STAGING_DIR}/opera

  cp ${WORKSPACE}/requirements*.txt \
     ${STAGING_DIR}/opera

  cp ${WORKSPACE}/.flake8 \
     ${STAGING_DIR}/opera

  cp ${WORKSPACE}/.pylintrc \
     ${STAGING_DIR}/opera
}

# Start the metrics collection of both docker stats and the miscellaneous os statistics.
# Parameters:
#     pge:  pge we are working on
#     container_name: Name given to the container when it is run via --name argument
#     results_dir: Directory where all files will be stored.
#     sample_time:  The time between sampling of the statistics.
metrics_collection_start()
{
  if $COLLECT_METRICS; then
      echo "Start Metrics Collection"
      local pge=$1
      local container_name=$2
      local results_dir=$3

      # If no sample_time value is passed - default to a value of 1
      if [[ -z "$4" ]]
      then
          local sample_time=1
      else
          local sample_time=$4
      fi

      echo "Using sample time of: $sample_time"

      # Initialize output files and statistics format
      metrics_stats="${results_dir}/${pge}_metrics_stats.csv"
      stats_pid_file="${results_dir}/${pge}_metrics_stats_bg_pid.txt"

      # initialize start seconds and the rest of the csv file's column titles
      METRICS_START_SECONDS=$SECONDS

      docker_stats_columns="{{.Name}},CPU,{{.CPUPerc}},MEM,{{.MemUsage}},MEM_PERC,{{.MemPerc}},NET,{{.NetIO}},BLOCK,{{.BlockIO}},PIDS,{{.PIDs}}"
      ds="docker stats --no-stream --format ${docker_stats_columns} ${container_name}";

      # Output the column titles
      echo "SECONDS,${docker_stats_columns},disk_used,swap_used,total_threads" > "$metrics_stats"

      # test for operating system
      if [[ $OSTYPE == "darwin"* ]]; then
          echo "Mac Operating system: $OSTYPE"
          os="mac"
      else
          echo "Linux Operating system: $OSTYPE"
          os="linux"
      fi

      # Use 'df' command to capture the amount of space on the filesystem (-B sets block size (1K)
      # the line represent Filesystem  1K-blocks  Used Blocks Available Blocks %Used Mounted_On
      if [[ $os == "linux" ]]; then
          block_space_cmd='df -B 1024 | grep /data'
      else
          # shellcheck disable=SC2089
          block_space_cmd='df -B 1024 | grep "/System/Volumes/VM"'
      fi

      # Get the number of system threads
      sys_threads_cmd='ps -elf | wc -l'

      if [[ $os == "linux" ]]; then
          # Use 'free' to get the total amount of Swap space available
          swap_space_cmd='free -g | grep Swap'
      else
          # shellcheck disable=SC2089
          swap_space_cmd='echo "N/A"'
      fi

      dus="eval $block_space_cmd"
      swu="eval $swap_space_cmd"
      ths="eval $sys_threads_cmd"

      { while true; do sleep "$sample_time"; \
        echo "$(metrics_seconds)", "`$ds`", "`$dus`", "`$swu`", "`$ths`" >> "${metrics_stats}"; done } & \
      echo "$!" > "${stats_pid_file}"
  fi
}

# End the metrics collection of both docker stats and the miscellaneous os statistics.
# Parameters:
#     pge: pge name
#     exit_code:  Exit code from Docker run (0 = success, non-zero = failure).
#     results_dir: the directory all files will be written to during the metrics collection.
#                  These intermediate file will be processed written to .csv files and deleted.
metrics_collection_end()
{
  if $COLLECT_METRICS; then
    local pge=$1
    local container=$2
    local exit_code=$3
    local results_dir=$4

    local metrics_stats="${results_dir}/${pge}_metrics_stats.csv"
    local stats_pid_file="${results_dir}/${pge}_metrics_stats_bg_pid.txt"

    # kill the background tasks (the pid number is stored in the file below)
    kill "$(cat "${stats_pid_file}")"
    wait "$(cat "${stats_pid_file}")" 2> /dev/null || true
    rm "${stats_pid_file}"

    if [[ $exit_code == 0 ]]
    then
      timestamp=$(date -u +'%Y%m%dT%H%M%SZ')
      processed_csv_file="${results_dir}/docker_metrics_${pge}_${container}_${timestamp}.csv"
      python3 "$SCRIPT_DIR"/../metrics/process_metric_data.py "$pge" "$container" "$metrics_stats" "$processed_csv_file"
      process_metrics_exit_code=$?
      if [[ $process_metrics_exit_code == 0 ]] && [ -f $processed_csv_file ]
      then
          metrics_plot_file="${results_dir}/docker_metrics_${pge}_${container}_${timestamp}.png"
          python3 "$SCRIPT_DIR"/../metrics/plot_metric_data.py "$processed_csv_file" "$metrics_plot_file"
          plot_metrics_exit_code=$?
          if [[ $plot_metrics_exit_code == 0 ]]
          then
              rm "$metrics_stats"
          else
              echo "An error occurred in plot_metric_data.py"
          fi
      else
          echo "An error occurred in process_metric_data.py"
      fi

      echo "metrics_collection has completed."
    else
      echo "Docker exited with an error: metrics will not be processed or uploaded."
    fi
  fi
}

metrics_seconds()
{
    echo $(( SECONDS - METRICS_START_SECONDS ))
}
