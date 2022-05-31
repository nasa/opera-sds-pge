#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

metrics_collection_start ()
{
    # container name should always contain pge_docker_tag, PGE, and runconfig (at a minimum)
    container_name=$1

    # Initialize output files and statistics format
    metrics_stats="${container_name}_metrics_stats.csv"

    # TODO miscellaneous statistics will be added in a future release
    # metrics_misc="${container_name}_metrics_misc.csv

    stat_format="{{.Name}},CPU,{{.CPUPerc}},MEM,{{.MemUsage}},MEM %,{{.MemPerc}},NET,{{.NetIO}},BLOCK,{{.BlockIO}},PIDS,{{.PIDs}}"

    # initialize start seconds and csv file contents - put on first line of each file
    METRICS_START_SECONDS=$SECONDS
    echo "SECONDS,$stat_format" > "$metrics_stats"
    # echo "SECONDS,disk_used,swap_used,total_threads,last_line" > $metrics_misc

    # start the background processes to monitor docker stats
    # TODO For the time being (may ultimately remove) take out the sleep ("$(metrics_seconds),$ds" >> ${metrics_stats}; sleep .1; done })
    { while true; do ds=$(docker stats --no-stream --format "${stat_format}" "${container_name}" 2>/dev/null); echo "$(metrics_seconds)","$ds" >> "${metrics_stats}"; done } &
    echo "$!" > "${container_name}_metrics_stats_bg_pid.txt"
}

metrics_collection_end ()
{
    container_name=$1
    exit_code=$2
    # TODO The variables below will be used in the future.
    # mce_pge=$3
    # mce_runconfig=$4

    echo "metrics_collection_end is terminating background metrics collection jobs."

    metrics_stats="${container_name}_metrics_stats.csv"
    # TODO for the time being taking out miscellaneous statistics
    # metrics_misc="${container_name}_metrics_misc.csv"

    # kill the background tasks
    kill "$(cat "${container_name}_metrics_stats_bg_pid.txt")"
    rm "${container_name}"_metrics_stats_bg_pid.txt
    # kill "$(cat "${container_name}_metrics_misc_bg_pid.txt")"
    # rm "${container_name}"_metrics_misc_bg_pid.txt

    if [[ $exit_code == 0 ]]
    then
        echo "metrics_collection_end is calling process_metric_data.py"
        python3 $SCRIPT_DIR/process_metric_data.py $metrics_stats
        process_metrics_exit_code=$?
        if [[ $process_metrics_exit_code == 0 ]]
        then
            echo 'New metrics file ran to completion'
        fi
    else
        echo "Docker exited with an error and so metrics will not be processed or uploaded (csv files will be saved)."
        echo "Error code: $process_metrics_exit_code"
    fi

    echo "metrics_collection_end has completed."
}

metrics_seconds()
{
    echo $(( SECONDS - METRICS_START_SECONDS ))
}
