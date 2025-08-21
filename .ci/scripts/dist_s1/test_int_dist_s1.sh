#!/bin/bash
# Script to execute integration tests on OPERA DIST-S1 PGE Docker image
#
set -e
umask 002


SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/../util/test_int_util.sh
. "$SCRIPT_DIR"/../util/util.sh

# Parse args
test_int_parse_args "$@"

echo '
================================================
Integration Testing DIST-S1 PGE docker image...
================================================
'

PGE_NAME="dist_s1"
PGE_IMAGE="opera_pge/${PGE_NAME}"
SAMPLE_TIME=1

# defaults, test data and runconfig files should be updated as-needed to use
# the latest available as defaults for use with the Jenkins pipeline call
# INPUT/OUTPUT_DATA should be the name of the corresponding archives in s3://operasds-dev-pge/dist_s1/
# RUNCONFIG should be the name of the runconfig file  in <repo_root>/.ci/scripts/dist-s1/
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath "$(dirname "$(realpath "$0")")"/../../..)
[ -z "${PGE_TAG}" ] && PGE_TAG="${USER}-dev"
[ -z "${INPUT_DATA}" ] && INPUT_DATA="dist_s1_calval_2.0.4_expected_input.zip "
[ -z "${EXPECTED_DATA}" ] && EXPECTED_DATA="dist_s1_calval_2.0.4_expected_output.zip "
[ -z "${RUNCONFIG}" ] && RUNCONFIG="opera_pge_dist_s1_r4_calval_runconfig.yaml"
[ -z "${TMP_ROOT}" ] && TMP_ROOT="$DEFAULT_TMP_ROOT"

# Create the test output directory in the work space
test_int_setup_results_directory

# Create a temporary directory to hold test data
test_int_setup_data_tmp_directory

# Download, extract and cd to test data directory
test_int_setup_test_data

# Setup cleanup on exit
trap test_int_trap_cleanup EXIT

# overall_status values and their meaning
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

input_data_basename=$(basename -- "$INPUT_DATA")
input_data_dir="${TMP_DIR}/${input_data_basename%.*}/input_dir"

expected_data_basename=$(basename -- "$EXPECTED_DATA")

expected_data_dir="${TMP_DIR}/${expected_data_basename%.*}/expected_output"

echo "Input data directory: ${input_data_dir}"
echo "Expected data directory: ${expected_data_dir}"

# the testdata reference metadata contains this path so we use it here
output_dir="${TMP_DIR}/output_dist_s1"

# make sure no output directory already exists
if [ -d "$output_dir" ]; then
    echo "Output directory $output_dir already exists (and should not). Removing directory."
    rm -rf "${output_dir}"
fi

echo "Creating output directory $output_dir."
mkdir -p "$output_dir"

# the testdata reference metadata contains this path so we use it here
scratch_dir="${TMP_DIR}/dist_s1_scratch/scratch_dir"

# make sure no scratch directory already exists
if [ -d "$scratch_dir" ]; then
    echo "Scratch directory $scratch_dir already exists (and should not). Removing directory.."
    rm -rf "${scratch_dir}"
fi
echo "Creating scratch directory $scratch_dir."
mkdir -p --mode=777 "$scratch_dir"

# Copy the Algorithm Parameters RunConfigs
algo_runconfig="opera_pge_dist_s1_r4_calval_algorithm_parameters.yaml"
local_algo_runconfig="${SCRIPT_DIR}/${algo_runconfig}"
echo "Copying runconfig file $local_algo_runconfig to $runconfig_dir"
cp ${local_algo_runconfig} ${runconfig_dir}

# Assign a container name to avoid the auto-generated one created by Docker
container_name="${PGE_NAME}"

# Start metrics collection
metrics_collection_start "$PGE_NAME" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

echo "Running Docker image ${PGE_IMAGE}:${PGE_TAG} for ${input_data_dir}"
docker run --rm -u $UID:"$(id -g)" --name $container_name \
            -v "${TMP_DIR}/runconfig":/home/ops/runconfig:ro \
            -v "$input_data_dir":/home/ops/input_dir:ro \
            -v "$output_dir":/home/ops/output_dir \
            -v "$scratch_dir":/home/ops/scratch_dir \
            -v "$expected_data_dir":/home/ops/expected_output_dir \
            ${PGE_IMAGE}:"${PGE_TAG}" --file /home/ops/runconfig/"$RUNCONFIG"

docker_exit_status=$?

# End metrics collection
metrics_collection_end "$PGE_NAME" "$container_name" "$docker_exit_status" "$TEST_RESULTS_DIR"

# Copy the PGE/SAS log file(s) to the test results directory so it can be archived
# by Jenkins with the other results
cp "${output_dir}"/*.log "${TEST_RESULTS_DIR}"
# Copy the results.html file to the same directory
cp "${output_dir}"/test_int_dist_s1_results.html "${TEST_RESULTS_DIR}"/test_int_dist_s1_results.html

if [ $docker_exit_status -ne 0 ]; then
  echo "docker exit indicates failure: ${docker_exit_status}"
  overall_status=1
else
  # Retrieve the return code written to disk by the comparison script
  test_status=$(cat "$output_dir/compare_dist_s1_products.rc")

  if [ $test_status -ne 0 ]; then
    overall_status=$test_status
  fi
fi

echo " "
if [ $overall_status -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi

exit $overall_status
