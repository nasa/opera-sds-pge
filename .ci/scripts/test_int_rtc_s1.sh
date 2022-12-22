#!/bin/bash
# Script to execute integration tests on OPERA RTC-S1 PGE Docker image
#
set -e
set -x
umask 002

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. $SCRIPT_DIR/test_int_util.sh
. $SCRIPT_DIR/util.sh

# Parse args
test_int_parse_args "$@"

echo '
================================================
Integration Testing RTC-S1 PGE docker image...
================================================
'

PGE_NAME="rtc_s1"
PGE_IMAGE="opera_pge/${PGE_NAME}"
SAMPLE_TIME=5

# defaults, test data and runconfig files should be updated as-needed to use
# the latest available as defaults for use with the Jenkins pipeline call
# TESTDATA should be the name of the test data archive in s3://operasds-dev-pge/${PGE_NAME}/
# RUNCONFIG should be the name of the runconfig in s3://operasds-dev-pge/${PGE_NAME}/
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../..)
[ -z "${PGE_TAG}" ] && PGE_TAG="${USER}-dev"
[ -z "${TESTDATA}" ] && TESTDATA="delivery_1_interface_0.1.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="rtc_s1.yaml"

# Create the test output directory in the workspace
test_int_setup_results_directory

# Create a temporary directory to hold test data
test_int_setup_data_tmp_directory

# Download, extract and cd to test data directory
test_int_setup_test_data

# Setup cleanup on exit
trap test_int_trap_cleanup EXIT

# Pull in product compare script from S3.
compare_script=rtc_compare.py
local_compare_script=${TMP_DIR}/${compare_script}
echo "Downloading s3://operasds-dev-pge/${PGE_NAME}/${compare_script} to ${local_compare_script}"
aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/${compare_script} ${local_compare_script}

# overall_status values and their meaning
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

# There is only 1 expected output directory for RTC-S1 
expected_dir="$(pwd)/peru/expected_output_dir"

# the testdata reference metadata contains this path so we use it here
output_dir="$(pwd)/output_rtc_s1"
# make sure no output directory already exissts
rmdir ${output_dir}
echo "Creating output directory $output_dir."
mkdir $output_dir

# the testdata reference metadata contains this path so we use it here
scratch_dir="$(pwd)/scratch_rtc_s1"
# make sure no scratch directory already exissts
rmdir ${scratch_dir}
echo "Creating scratch directory $scratch_dir."
mkdir $scratch_dir

container_name="${PGE_NAME}"

# Start metrics collection
metrics_collection_start "$PGE_NAME" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

echo "Running Docker image ${PGE_IMAGE}:${PGE_TAG}"

docker run --rm -u $UID:$(id -g) -n $container_name -w /home/rtc_user\
           -v $(pwd):/home/rtc_user/runconfig:ro \
           -v $(pwd)/peru:/home/rtc_user/input_dir:ro \
           -v ${output_dir}:/home/rtc_user/output_dir \
           -v ${scratch_dir}:/home/rtc_user/scratch_dir \
           ${PGE_IMAGE}:${PGE_TAG} --file /home/rtc_user/runconfig/${RUNCONFIG}

docker_exit_status=$?

# End metrics collection
metrics_collection_end "$PGE_NAME" "$docker_exit_status" "$TEST_RESULTS_DIR"

if [ $docker_exit_status -ne 0 ]; then
    echo "docker exit indicates failure: ${docker_exit_status}"
    overall_status=1
else

    declare -a burst_ids=( "t069_147170_iw1"
                           "t069_147170_iw3"
                           "t069_147171_iw1"
                           "t069_147171_iw2"
                           "t069_147171_iw3"
                           "t069_147172_iw1"
                           "t069_147172_iw2"
                           "t069_147172_iw3"
                           "t069_147173_iw1"
                           "t069_147173_iw2"
                           "t069_147173_iw3"
                           "t069_147174_iw1"
                           "t069_147174_iw2"
                           "t069_147174_iw3"
                           "t069_147175_iw1"
                           "t069_147175_iw2"
                           "t069_147175_iw3"
                           "t069_147176_iw1"
                           "t069_147176_iw2"
                           "t069_147176_iw3"
                           "t069_147177_iw1"
                           "t069_147177_iw2"
                           "t069_147177_iw3"
                           "t069_147178_iw1"
                           "t069_147178_iw2"
                           "t069_147178_iw3"
                           "t069_147179_iw2"
                           "t069_147179_iw3")

    echo "<tr><th>Compare Result</th><th><ul><li>Expected file</li><li>Output file</li></ul></th><th>rtc_compare.py output</th></tr>" >> $RESULTS_FILE
    for burst_id in "${burst_ids[@]}"; do
        echo "Comparing results for $burst_id"

        burst_id_uppercase=${burst_id^^}
        burst_id_replace_underscores=${burst_id_uppercase//_/-}
        burst_id_pattern="*_${burst_id_replace_underscores}_*.nc"
        output_file=$(ls $output_dir/$burst_id_pattern)
        echo $output_file
        expected_file=${expected_dir}/${burst_id}/rtc_product.nc
        compare_output=$(python3 ${local_compare_script} ${expected_file} ${output_file})

        echo "$compare_output"
        if [[ "$compare_output" != *"FAILED"* ]]; then
            echo "Product validation was successful for $output_file"
            compare_result="PASS"
        else
            echo "Failure: Some comparisons failed for $output_file"
            compare_result="FAIL"
            overall_status=2
        fi

        # remove ansi colors from string
        compare_output=$(echo "$compare_output" | sed -e 's/\x1b\[[0-9;]*m//g')
        # add html breaks to newlines
        compare_output=${compare_output//$'\n'/<br>$'\n'}
        echo "<tr><td>${compare_result}</td><td><ul><li>${expected_file}</li><li>${output_file}</li></ul></td><td>${compare_output}</td></tr>" >> $RESULTS_FILE
    done

fi
echo " "

if [ $overall_status -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi

exit $overall_status
