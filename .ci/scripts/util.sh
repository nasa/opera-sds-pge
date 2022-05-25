#!/bin/bash

metrics_collection_start ()
{
    # container name should always contain ghrVersion, PGE, and runconfig (at a minimum)
    container_name=$1

    # Initialize output files and statistics format
    metrics_stats="${container_name}_metrics_stats.csv"
#    metrics_misc="${container_name}_metrics_misc.csv"
    stat_format="{{.Name}},CPU,{{.CPUPerc}},MEM,{{.MemUsage}},MEM %,{{.MemPerc}},NET,{{.NetIO}},BLOCK,{{.BlockIO}},PIDS,{{.PIDs}}"

    # initialize start seconds and csv file contents - put on first line of each file
    METRICS_START_SECONDS=$SECONDS
    echo "SECONDS,$stat_format" > $metrics_stats
#    echo "SECONDS,disk_used,swap_used,total_threads,last_line" > $metrics_misc

    # start the background processes to monitor docker stats and disk use
    # For the time being take out the sleep ("$(metrics_seconds),$ds" >> ${metrics_stats}; sleep .1; done })
    { while true; do ds=$(docker stats --no-stream --format "${stat_format}" ${container_name} 2>/dev/null); echo "$(metrics_seconds),$ds" >> ${metrics_stats}; done } &
    echo "$!" > "${container_name}_metrics_stats_bg_pid.txt"
}

metrics_collection_end ()
{
    container_name=$1
    exit_code=$2
    mce_pge=$3
    mce_runconfig=$4

    echo "metrics_collection_end is terminating background metrics collection jobs"

    metrics_stats="${container_name}_metrics_stats.csv"
#    metrics_misc="${container_name}_metrics_misc.csv"

    # kill the background tasks
    kill "$(cat "${container_name}_metrics_stats_bg_pid.txt")"
#    rm "${container_name}"_metrics_stats_bg_pid.txt
#    kill "$(cat "${container_name}_metrics_misc_bg_pid.txt")"
#    rm "${container_name}"_metrics_misc_bg_pid.txt

    echo "metrics_collection_end is done"
}

metrics_seconds ()
{
    echo $(( SECONDS - METRICS_START_SECONDS ))
}
