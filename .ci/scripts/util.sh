#!/bin/bash

metrics_collection_start ()
{
  container_name=$1
  echo "$container_name"
  echo "call worked ok"
  METRICS_START_SECONDS=$SECONDS

#    if [ -z "$USER_APIKEY" ]
#    then
#        echo "USER_APIKEY needs to be set to your Artifactory API Key to upload results"
#        exit
#    fi
#
#    # container name should always contain ghrVersion, PGE, and runconfig (at a minimum)
#    container_name=$1
#
  metrics_stats="${container_name}_metrics_stats.csv"
  echo $metrics_stats
#    metrics_misc="${container_name}_metrics_misc.csv"
  stat_format="{{.Name}},CPU,{{.CPUPerc}},MEM,{{.MemUsage}},MEM %,{{.MemPerc}},NET,{{.NetIO}},BLOCK,{{.BlockIO}},PIDS,{{.PIDs}}"

  # initialize start seconds and csv file contents
  METRICS_START_SECONDS=$SECONDS
  echo $METRICS_START_SECONDS
  echo "SECONDS,$stat_format" > "$metrics_stats"
#    echo "SECONDS,disk_used,swap_used,total_threads,last_line" > "$metrics_misc"
#
#    # aws machines and swot-dev-1 use different partitions for data storage
#    hn=$(hostname)
#    if [ "$hn" = "swot-dev-pge.jpl.nasa.gov" ]
#    then
#        # this may be affected by other users doing things on the shared machine
#        dus_cmd='df -B 1024 | grep "/export/scratch"'
#    else
#        dus_cmd='df -B 1024 | grep "/dev/" | grep "/data"'
#    fi
#
   # get total system threads
   ths_cmd='ps -eLF | wc -l'

   # swap used
   swu_cmd='free -g | grep Swap'
#
#   if [ -z "${working}" ]
#   then
#       lll_dir=$PWD
#   else
#       lll_dir=${working}
#   fi
#    lll_file="last_log_line.txt"
#    find "${lll_dir}" -name ${lll_file} -exec rm {} \; 2>/dev/null
#    lll_cmd="echo $(find "${lll_dir}" -name ${lll_file} -exec cat {} \; 2>/dev/null)"
#
#    # start the background processes to monitor docker stats and disk use
#    { while true;
#      do
#          ds=$(docker stats --no-stream --format "${stat_format}" "${container_name}" 2>/dev/null)
#          echo "$(metrics_seconds),$ds" >> "${metrics_stats}"
#          sleep .1
#      done
#    } &
#    echo "$!" >> "${container_name}_metrics_stats_bg_pid.txt"
#    { while true
#      do
#          dus=$(eval "$dus_cmd")
#          swu=$(eval "$swu_cmd")
#          ths=$(eval "$ths_cmd")
#          lll=$(eval "$lll_cmd")
#          echo "$(metrics_seconds),$dus,$swu,$ths,$lll" >> "${metrics_misc}"
#          sleep 1
#      done
#    } &
#    echo "$!" >> "${container_name}_metrics_misc_bg_pid.txt"
#}
#
#metrics_collection_end ()
#{
#    container_name=$1
#    exit_code=$2
#    mce_pge=$3
#    mce_runconfig=$4
#
#    echo "metrics_collection_end is terminating background metrics collection jobs"
#
#    metrics_stats="${container_name}_metrics_stats.csv"
#    metrics_misc="${container_name}_metrics_misc.csv"
#
#    # kill the background tasks
#    kill "$(cat "${container_name}_metrics_stats_bg_pid.txt")"
#    rm "${container_name}"_metrics_stats_bg_pid.txt
#    kill "$(cat "${container_name}_metrics_misc_bg_pid.txt")"
#    rm "${container_name}"_metrics_misc_bg_pid.txt
#
#    if [[ $exit_code == 0 ]]
#    then
#        echo "metrics_collection_end is calling process_metric_data.py"
#        python3 "${basedir}"/tools/process_metric_data.py "$ghrVersion" "$mce_pge" "$mce_runconfig" "$container_name" "$metrics_stats" "$metrics_misc"
#        process_metrics_exit_code=$?
#        if [[ $process_metrics_exit_code == 0 ]]
#        then
#            rm "$metrics_stats"
#            rm "$metrics_misc"
#        fi
#    else
#        echo "docker exited with an error and so metrics will not be processed or uploaded. csv files will be kept."
#    fi
#    find "${lll_dir}" -name ${lll_file} -exec rm {} \; 2>/dev/null
#    echo "metrics_collection_end is done"
#}

metrics_seconds ()
{
    echo $(( SECONDS - METRICS_START_SECONDS ))
}

}