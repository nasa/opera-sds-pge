#!/usr/bin/env bash
#
# Copyright 2022, by the California Institute of Technology.
# ALL RIGHTS RESERVED.
# United States Government sponsorship acknowledged.
# Any commercial use must be negotiated with the Office of Technology Transfer
# at the California Institute of Technology.
# This software may be subject to U.S. export control laws and regulations.
# By accepting this document, the user agrees to comply with all applicable
# U.S. export laws and regulations. User has the responsibility to obtain
# export licenses, or other export authority as may be required, before
# exporting such information to foreign countries or providing access to
# foreign persons.
#
# This script is basically a wrapper, it runs the command specified as
# a command line argument, plus it outputs execution statistics to a file.
#
# Usage:
# pge_run_docker_stats.sh <command> [arg...] [--stats filename]
#
# where [--stats <filename>] specifies the filename of the statistics output.
# This argument can come in any order, before [arg...] or before the <command>,
# it does not matter.  The entire command line arguments are searched, and
# if --stats <filename> is found, that pair of arguments is intercepted.
co
set -e

DOCKER_ENTRYPOINT_SCRIPT_DIR=$(dirname ${BASH_SOURCE[0]})
original_args=("$@")
pass_through_args=()

# default execution statistics filename
stats_filename='/home/conda/output_dir/_docker_stats.json'

# Most of the command line arguments get passed through to the
# command, but pick out the stats filename (if specified)
while test $# -gt 0
do
  case "$1" in
    --stats)
      # Intercept the stats output filename
      if [[ ! (-z "$2") ]] && [[ "$2" != -* ]]; then
        stats_filename=$2
        shift
      fi
      ;;
    -h|--help)
      # Do the PGE's --help without execution statistics
      "${original_args[@]}"
      echo -e "\n\nIn addition to the above usage usage information,"
      echo -e "an additional optional argument is supported"
      echo -e "by the wrapper:\n\n"
      echo -e "  --stats FILE  specifies the name of the output file where execution"
      echo -e "                statistics are written\n\n"
      exit 0
      ;;
    *)
      pass_through_args[${#pass_through_args[@]}]=$1
      ;;
  esac
  shift
done

echo "Execution statistics will be output to file: ${stats_filename}"
# create the directory for the stats file if necessary
stats_dir=$(dirname ${stats_filename})
[[ -z "$stats_dir" ]] || [[ "$stats_dir" == '.' ]] || mkdir -p "$stats_dir"
echo "Directory holding execution statistics: ${stats_dir}"

$DOCKER_ENTRYPOINT_SCRIPT_DIR/docker-stats-on-exit-shim "${stats_filename}" "${pass_through_args[@]}"
