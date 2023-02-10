#!/bin/bash
# Script to execute integration tests on OPERA CSLC_S1 PGE Docker image
#
set -e
umask 002

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/test_int_util.sh
. "$SCRIPT_DIR"/util.sh

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
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath "$(dirname "$(realpath "$0")")"/../..)
[ -z "${PGE_TAG}" ] && PGE_TAG="${USER}-dev"
[ -z "${INPUT_DATA}" ] && INPUT_DATA="delivery_cslc_s1_beta_0.1_input_data.zip"
[ -z "${EXPECTED_DATA}" ] && EXPECTED_DATA="delivery_cslc_s1_beta_0.1_expected_output_dir.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="delivery_cslc_s1_beta_0.1_runconfig.yaml"
[ -z "${TMP_ROOT}" ] && TMP_ROOT="$DEFAULT_TMP_ROOT"

# Create the test output directory in the workspace
test_int_setup_results_directory

# Create a temporary directory to hold test data
test_int_setup_data_tmp_directory

# Download, extract and cd to test data directory
test_int_setup_test_data

# Setup cleanup on exit
trap test_int_trap_cleanup EXIT

# Pull in validation script from S3.
# Current source is https://raw.githubusercontent.com/opera-adt/COMPASS/c77b1a681e85d44c19baf2cf1eaf88f901b12bc9/src/compass/utils/validate_cslc.py
local_validate_cslc=${TMP_DIR}/validate_cslc.py
echo "Downloading s3://operasds-dev-pge/${PGE_NAME}/validate_cslc.py to $local_validate_cslc"
aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/validate_cslc.py "$local_validate_cslc"

# overall_status values and their meanings
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

# There is only 1 expected output directory for CSLC_S1
expected_dir="${TMP_DIR}/${EXPECTED_DATA%.*}/expected_output_dir"
input_dir="${TMP_DIR}/${INPUT_DATA%.*}/input_data"
runconfig_dir="${TMP_DIR}/runconfig"

# the testdata reference metadata contains this path so we use it here
output_dir="${TMP_DIR}/output_cslc_s1"
# make sure no output directory already exists
if [ -d "$output_dir" ]; then
    echo "Output directory $output_dir already exists (and should not). Removing directory."
    rm -rf "${output_dir}"
fi
echo "Creating output directory $output_dir."
mkdir -p "$output_dir"

# the testdata reference metadata contains this path so we use it here
scratch_dir="${TMP_DIR}/scratch_cslc_s1"
# make sure no scratch directory already exists
if [ -d "$scratch_dir" ]; then
    echo "Scratch directory $scratch_dir already exists (and should not). Removing directory."
    rm -rf "${scratch_dir}"
fi
echo "Creating scratch directory $scratch_dir."
mkdir -p --mode=777 "$scratch_dir"

container_name="${PGE_NAME}"

# Start metrics collection
metrics_collection_start "$PGE_NAME" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

echo "Running Docker image ${PGE_IMAGE}:${PGE_TAG}"

docker run --rm -u $UID:"$(id -g)" -w /home/compass_user --name $container_name \
           -v "${runconfig_dir}":/home/compass_user/runconfig:ro \
           -v "${input_dir}":/home/compass_user/input_dir:ro \
           -v "${output_dir}":/home/compass_user/output_dir \
           -v "${scratch_dir}":/home/compass_user/scratch_s1_cslc \
           ${PGE_IMAGE}:"${PGE_TAG}" --file /home/compass_user/runconfig/"$RUNCONFIG"

docker_exit_status=$?

# End metrics collection
metrics_collection_end "$PGE_NAME" "$docker_exit_status" "$TEST_RESULTS_DIR"

if [ $docker_exit_status -ne 0 ]; then
    echo "docker exit indicates failure: ${docker_exit_status}"
    overall_status=1
else
    echo "<tr><th>Compare Result</th><th><ul><li>Expected file</li><li>Output file</li></ul></th><th>validate_cslc.py output</th></tr>" >> "$RESULTS_FILE"
    declare -a burst_ids=(  "t064_135518_iw1"
                            "t064_135518_iw2"
                            "t064_135518_iw3"
                            "t064_135519_iw1"
                            "t064_135519_iw2"
                            "t064_135519_iw3"
                            "t064_135520_iw1"
                            "t064_135520_iw2"
                            "t064_135520_iw3"
                            "t064_135521_iw1"
                            "t064_135521_iw2"
                            "t064_135521_iw3"
                            "t064_135522_iw1"
                            "t064_135522_iw2"
                            "t064_135522_iw3"
                            "t064_135523_iw1"
                            "t064_135523_iw2"
                            "t064_135523_iw3"
                            "t064_135524_iw1"
                            "t064_135524_iw2"
                            "t064_135524_iw3"
                            "t064_135525_iw1"
                            "t064_135525_iw2"
                            "t064_135525_iw3"
                            "t064_135526_iw1"
                            "t064_135526_iw2"
                            "t064_135526_iw3"
                            "t064_135527_iw1")

    for burst_id in "${burst_ids[@]}"; do
        compare_result="PENDING"
        echo "-------------------------------------"
        echo "Comparing results for burst id ${burst_id}"
        burst_id_uppercase=${burst_id^^}
        burst_id_replace_underscores=${burst_id_uppercase//_/-}
        burst_id_pattern="*_${burst_id_replace_underscores}_*.h5"
        output_file=`ls $output_dir/$burst_id_pattern`
        echo "Ouput file matching burst id is $output_file"

        ref_product="/exp/${burst_id}/20220501/${burst_id}_20220501_VV.h5"
        sec_product="/out/$(basename ${output_file})"
        docker_out=$(docker run --rm -u compass_user:compass_user \
                                -v "${TMP_DIR}":/working:ro \
                                -v "${output_dir}":/out:ro \
                                -v "${expected_dir}":/exp:ro \
                                --entrypoint /home/compass_user/miniconda3/envs/COMPASS/bin/python3 \
                                ${PGE_IMAGE}:"${PGE_TAG}" \
                                /working/validate_cslc.py \
                                --ref-product ${ref_product} \
                                --sec-product ${sec_product} 2>&1) || docker_exit_status=$?

        echo "$docker_out"
        if [[ "$docker_out" != *"All CSLC product checks have passed"* ]]; then
            echo "Failure: All CSLC product checks DID NOT PASS"
            compare_result="FAIL"
            overall_status=2
        elif [[ "$docker_out" != *"All CSLC metadata checks have passed"* ]]; then
            echo "Failure: All CSLC metadata checks DID NOT PASS"
            compare_result="FAIL"
            overall_status=2
        else
            echo "Product validation was successful"
            compare_result="PASS"
        fi

        docker_out="${docker_out//$'\n'/<br>}"
        echo "<tr><td>${compare_result}</td><td><ul><li>${ref_product}</li><li>${sec_product}</li></ul></td><td>${docker_out}</td></tr>" >> "$RESULTS_FILE"
    done
fi
echo " "

if [ $overall_status -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi

exit $overall_status
