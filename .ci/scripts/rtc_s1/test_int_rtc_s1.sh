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
[ -z "${INPUT_DATA}" ] && INPUT_DATA="rtc_s1_delivery_5.1_final_1.0.1_expected_input.zip"
[ -z "${EXPECTED_DATA}" ] && EXPECTED_DATA="rtc_s1_delivery_5.1_final_1.0.1_expected_output.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="opera_pge_rtc_s1_delivery_5_final_runconfig.yaml"
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
static_runconfig="opera_pge_rtc_s1_static_delivery_5_final_runconfig.yaml"
local_static_runconfig="${SCRIPT_DIR}/${static_runconfig}"
echo "Copying runconfig file $local_static_runconfig to $runconfig_dir/"
cp ${local_static_runconfig} ${runconfig_dir}

# Pull in product compare script from S3.
# Current source is https://raw.githubusercontent.com/opera-adt/RTC/main/app/rtc_compare.py
local_compare_script=${TMP_DIR}/rtc_compare.py
echo "Downloading s3://operasds-dev-pge/${PGE_NAME}/rtc_compare_final_1.0.0.py to ${local_compare_script}"
aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/rtc_compare_calval_0.4.1.py "$local_compare_script"

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

if [ $overall_status -eq 0 ]; then
    initialize_html_results_file "$output_dir" "$PGE_NAME"
    echo "<tr><th>Compare Result</th><th><ul><li>Expected file</li><li>Output file</li></ul></th><th>rtc_s1_compare.py output</th></tr>" >> "$RESULTS_FILE"

    declare -a burst_ids=("t069_147169_iw3"
                          "t069_147170_iw3"
                          "t069_147171_iw3"
                          "t069_147172_iw3"
                          "t069_147173_iw3"
                          "t069_147174_iw3"
                          "t069_147175_iw3"
                          "t069_147176_iw3"
                          "t069_147177_iw3"
                          "t069_147178_iw3")

    for burst_id in "${burst_ids[@]}"; do
        rtc_compare_result="PENDING"
        expected_dir="${TMP_DIR}/${EXPECTED_DATA%.*}/expected_rtc_s1_output_dir"

        echo "-------------------------------------"
        echo "Comparing results for burst id $burst_id"

        burst_id_uppercase=${burst_id^^}
        burst_id_replace_underscores=${burst_id_uppercase//_/-}
        burst_id_pattern="OPERA_L2_RTC-S1_${burst_id_replace_underscores}_*"
        output_files="${output_dir}/${burst_id}"
        expected_files="${expected_dir}/${burst_id}"

        # Move the products for the current burst ID into their own subdir to compare
        # against the expected
        mkdir -p "${output_files}"
        mv ${output_dir}/${burst_id_pattern} ${output_files}

        echo "Output RTC files matching burst id are in $output_files"
        echo "Expected files are in $expected_files"

        compare_output=$("${SCRIPT_DIR}"/../rtc_s1/rtc_s1_compare.py "${expected_files}" "${output_files}")

        echo "$compare_output"
        if [[ "$compare_output" != *"FAILED"* ]]; then
            echo "Product validation was successful for $output_files"
            rtc_compare_result="PASS"
        else
            echo "Failure: Some comparisons failed for $output_files"
            rtc_compare_result="FAIL"
            overall_status=2
        fi

        # remove ansi colors from string
        compare_output="$(echo "$compare_output" | sed -e 's/\x1b\[[0-9;]*m//g')"

        # add html breaks to newlines
        compare_output=${compare_output//$'\n'/<br>$'\n'}
        update_html_results_file "${rtc_compare_result}" "${expected_files}" "${output_files}" "${compare_output}"

        static_layers_compare_result="PENDING"
        expected_dir="${TMP_DIR}/${EXPECTED_DATA%.*}/expected_rtc_s1_static_output_dir"

        static_burst_id_pattern="OPERA_L2_RTC-S1-STATIC_${burst_id_replace_underscores}_*.tif"
        output_static_files="${static_output_dir}/${burst_id}"
        expected_static_files="${expected_dir}/${burst_id}"

        # Move the products for the current burst ID into their own subdir to compare
        # against the expected
        mkdir -p "${output_static_files}"
        mv ${static_output_dir}/${static_burst_id_pattern} ${output_static_files}

        echo "Output static layers matching burst id are in $output_static_files"
        echo "Expected files are in $expected_static_files"

        compare_output=$("${SCRIPT_DIR}"/../rtc_s1/rtc_s1_compare.py "${expected_static_files}" "${output_static_files}")

        echo "$compare_output"
        if [[ "$compare_output" != *"FAILED"* ]]; then
            echo "Product validation was successful for $output_static_files"
            static_layers_compare_result="PASS"
        else
            echo "Failure: Some comparisons failed for $output_static_files"
            static_layers_compare_result="FAIL"
            overall_status=2
        fi

        # remove ansi colors from string
        compare_output="$(echo "$compare_output" | sed -e 's/\x1b\[[0-9;]*m//g')"

        # add html breaks to newlines
        compare_output=${compare_output//$'\n'/<br>$'\n'}
        update_html_results_file "${static_layers_compare_result}" "${expected_static_files}" "${output_static_files}" "${compare_output}"
    done

    finalize_html_results_file
    cp "${output_dir}"/test_int_rtc_s1_results.html "${TEST_RESULTS_DIR}"/test_int_rtc_s1_results.html
fi
echo " "

if [ $overall_status -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi

exit $overall_status
