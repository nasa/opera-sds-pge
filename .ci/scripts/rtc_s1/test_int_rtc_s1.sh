#!/bin/bash
# Script to execute integration tests on OPERA RTC-S1 PGE Docker image
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
Integration Testing RTC-S1 PGE docker image...
================================================
'

PGE_NAME="rtc_s1"
PGE_IMAGE="opera_pge/${PGE_NAME}"
SAMPLE_TIME=15

# defaults, test data and runconfig files should be updated as-needed to use
# the latest available as defaults for use with the Jenkins pipeline call
# INPUT/OUTPUT_DATA should be the name of the test data archive in s3://operasds-dev-pge/${PGE_NAME}/
# RUNCONFIG should be the name of the runconfig in s3://operasds-dev-pge/${PGE_NAME}/
[ -z "${WORKSPACE}" ] && WORKSPACE="$(realpath "$(dirname "$(realpath "$0")")"/../../..)"
[ -z "${PGE_TAG}" ] && PGE_TAG="${USER}-dev"
[ -z "${INPUT_DATA}" ] && INPUT_DATA="rtc_s1_final_1.0.2_expected_input_data.zip"
[ -z "${EXPECTED_DATA}" ] && EXPECTED_DATA="rtc_s1_final_1.0.2_expected_output.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="opera_pge_rtc_s1_delivery_5.2_final_runconfig.yaml"
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

input_dir="${TMP_DIR}/${INPUT_DATA%.*}/input_dir"
runconfig_dir="${TMP_DIR}/runconfig"

# Copy the RunConfig for the static layers workflow
static_runconfig="opera_pge_rtc_s1_static_delivery_5.2_final_runconfig.yaml"
local_static_runconfig="${SCRIPT_DIR}/${static_runconfig}"
echo "Copying runconfig file $local_static_runconfig to $runconfig_dir/"
cp ${local_static_runconfig} ${runconfig_dir}

### Pull in product compare script from S3.
### Current source is https://raw.githubusercontent.com/opera-adt/RTC/main/app/rtc_compare.py
###local_compare_script=${TMP_DIR}/rtc_compare.py
##echo "Downloading s3://operasds-dev-pge/${PGE_NAME}/rtc_compare_final_1.0.0.py to ${local_compare_script}"
##aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/rtc_compare_calval_0.4.1.py "$local_compare_script"

# the testdata reference metadata contains this path so we use it here
output_dir="${TMP_DIR}/rtc_s1_output_dir"
static_output_dir="${TMP_DIR}/rtc_s1_static_output_dir"

# make sure no output directory already exists
if [ -d "$output_dir" ]; then
    echo "Output directory $output_dir already exists (and should not). Removing directory."
    rm -rf "${output_dir}"
fi
echo "Creating output directories $output_dir and $static_output_dir."
mkdir -p "$output_dir"
mkdir -p "$static_output_dir"

# the testdata reference metadata contains this path so we use it here
scratch_dir="${TMP_DIR}/scratch_rtc_s1"

# make sure no scratch directory already exists
if [ -d "$scratch_dir" ]; then
    echo "Scratch directory $scratch_dir already exists (and should not). Removing directory..."
    rm -rf "${scratch_dir}"
fi

echo "Creating scratch directory $scratch_dir."
mkdir -p --mode=777 "$scratch_dir"


container_name="${PGE_NAME}"

# Start metrics collection
metrics_collection_start "$PGE_NAME" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

echo "Running Docker image ${PGE_IMAGE}:${PGE_TAG} with baseline workflow"

docker run --rm -u $UID:"$(id -g)" --env OMP_NUM_THREADS=3 \
                -w /home/rtc_user --name $container_name \
                -v "${runconfig_dir}":/home/rtc_user/runconfig:ro \
                -v "${input_dir}"/:/home/rtc_user/input_dir:ro \
                -v "${output_dir}":/home/rtc_user/output_dir \
                -v "${scratch_dir}":/home/rtc_user/scratch_dir \
                ${PGE_IMAGE}:"${PGE_TAG}" --file /home/rtc_user/runconfig/${RUNCONFIG}

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

docker run --rm -u $UID:"$(id -g)" --env OMP_NUM_THREADS=3 \
           -w /home/rtc_user --name $container_name \
           -v "${runconfig_dir}":/home/rtc_user/runconfig:ro \
           -v "${input_dir}"/:/home/rtc_user/input_dir:ro \
           -v "${static_output_dir}":/home/rtc_user/output_dir \
           -v "${scratch_dir}":/home/rtc_user/scratch_dir \
           ${PGE_IMAGE}:"${PGE_TAG}" --file /home/rtc_user/runconfig/"$static_runconfig"

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
