#!/bin/bash
# Script to execute integration tests on OPERA CSLC_S1 PGE Docker image
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
Integration Testing CSLC_S1 PGE docker image...
================================================
'

PGE_NAME="cslc_s1"
PGE_IMAGE="opera_pge/${PGE_NAME}"
SAMPLE_TIME=15

# Defaults, test data and runconfig files should be updated as-needed to use
# the latest available as defaults for use with the Jenkins pipeline call.
# Test data should be uploaded to  s3://operasds-dev-pge/${PGE_NAME}/
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath "$(dirname "$(realpath "$0")")"/../../..)
[ -z "${PGE_TAG}" ] && PGE_TAG="${USER}-dev"
[ -z "${INPUT_DATA}" ] && INPUT_DATA="cslc_s1_final_0.5.5_expected_input_data.zip"
[ -z "${EXPECTED_DATA}" ] && EXPECTED_DATA="cslc_s1_final_0.5.5_expected_output.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="opera_pge_cslc_s1_delivery_6.4_final_runconfig.yaml"
[ -z "${TMP_ROOT}" ] && TMP_ROOT="$DEFAULT_TMP_ROOT"

# Create the test output directory in the workspace
test_int_setup_results_directory

# Create a temporary directory to hold test data
test_int_setup_data_tmp_directory

# Download, extract and cd to test data directory
test_int_setup_test_data

# Setup cleanup on exit
trap test_int_trap_cleanup EXIT

# overall_status values and their meanings
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

input_dir="${TMP_DIR}/${INPUT_DATA%.*}/input_data"
runconfig_dir="${TMP_DIR}/runconfig"

# Copy the RunConfig for the static layers workflow
static_runconfig="opera_pge_cslc_s1_static_delivery_6.4_final_runconfig.yaml"
local_static_runconfig="${SCRIPT_DIR}/${static_runconfig}"
echo "Copying runconfig file $local_static_runconfig to $runconfig_dir/"
cp ${local_static_runconfig} ${runconfig_dir}

# the testdata reference metadata contains this path so we use it here
output_dir="${TMP_DIR}/output_cslc_s1"
static_output_dir="${TMP_DIR}/output_cslc_s1_static"

# make sure no output directory already exists
if [ -d "$output_dir" ]; then
    echo "Output directory $output_dir already exists (and should not). Removing directory."
    rm -rf "${output_dir}"
fi
echo "Creating output directories $output_dir and $static_output_dir."
mkdir -p "$output_dir"
mkdir -p "$static_output_dir"

# the testdata reference metadata contains this path so we use it here
scratch_dir="${TMP_DIR}/scratch_cslc_s1"

# make sure no scratch directory already exists
if [ -d "$scratch_dir" ]; then
    echo "Scratch directory $scratch_dir already exists (and should not). Removing directory."
    rm -rf "${scratch_dir}"
fi
echo "Creating scratch directory $scratch_dir."
mkdir -p --mode=777 "$scratch_dir"

# Get the number of available cores so we can limit utilization by the SAS
num_cores=$((`nproc --all`))

container_name="${PGE_NAME}"

# Start metrics collection
metrics_collection_start "$PGE_NAME" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

echo "Running Docker image ${PGE_IMAGE}:${PGE_TAG} with baseline workflow"

docker run --rm -u $UID:"$(id -g)" --env OMP_NUM_THREADS=$((num_cores-1)) \
                -w /home/compass_user/scratch --name $container_name \
                -v "${runconfig_dir}":/home/compass_user/runconfig:ro \
                -v "${input_dir}":/home/compass_user/input_dir:ro \
                -v "${output_dir}":/home/compass_user/output_dir \
                -v "${scratch_dir}":/home/compass_user/scratch_s1_cslc \
                ${PGE_IMAGE}:"${PGE_TAG}" --file /home/compass_user/runconfig/"$RUNCONFIG"

docker_exit_status=$?

# End metrics collection
metrics_collection_end "$PGE_NAME" "$container_name" "$docker_exit_status" "$TEST_RESULTS_DIR"

if [ $docker_exit_status -ne 0 ]; then
    echo "docker exit indicates failure: ${docker_exit_status}"
    overall_status=1
fi

# Run the static layer workflow
container_name="${PGE_NAME}_static"

# Start metrics collection
metrics_collection_start "${PGE_NAME}_static" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

echo "Running Docker image ${PGE_IMAGE}:${PGE_TAG} with static layer workflow"

docker run --rm -u $UID:"$(id -g)" --env OMP_NUM_THREADS=$((num_cores-1)) \
                -w /home/compass_user/scratch --name $container_name \
                -v "${runconfig_dir}":/home/compass_user/runconfig:ro \
                -v "${input_dir}":/home/compass_user/input_dir:ro \
                -v "${static_output_dir}":/home/compass_user/output_dir \
                -v "${scratch_dir}":/home/compass_user/scratch_s1_cslc \
                ${PGE_IMAGE}:"${PGE_TAG}" --file /home/compass_user/runconfig/"$static_runconfig"

docker_exit_status=$?

# End metrics collection
metrics_collection_end "${PGE_NAME}_static" "$container_name" "$docker_exit_status" "$TEST_RESULTS_DIR"

if [ $docker_exit_status -ne 0 ]; then
    echo "docker exit indicates failure: ${docker_exit_status}"
    overall_status=1
fi

# Copy the PGE/SAS log file(s) to the test results directory so it can be archived
# by Jenkins with the other results
cp "${output_dir}"/*.log "${TEST_RESULTS_DIR}"
cp "${static_output_dir}"/*.log "${TEST_RESULTS_DIR}"

if [ $overall_status -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi

exit $overall_status
