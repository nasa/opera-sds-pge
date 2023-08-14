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
[ -z "${INPUT_DATA}" ] && INPUT_DATA="delivery_cslc_s1_calval_0.4.0_expected_input_data.zip"
[ -z "${EXPECTED_DATA}" ] && EXPECTED_DATA="delivery_cslc_s1_calval_0.4.0_expected_output.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="opera_pge_cslc_s1_delivery_5.1_calval_runconfig.yaml"
[ -z "${TMP_ROOT}" ] && TMP_ROOT="$DEFAULT_TMP_ROOT"

# Create the test output directory in the workspace
test_int_setup_results_directory

# Create a temporary directory to hold test data
test_int_setup_data_tmp_directory

# Download, extract and cd to test data directory
test_int_setup_test_data

# Setup cleanup on exit
trap test_int_trap_cleanup EXIT

# Download the RunConfig for the static layers workflow
static_runconfig="opera_pge_cslc_s1_static_delivery_5.1_calval_runconfig.yaml"
local_static_runconfig="${TMP_DIR}/runconfig/${static_runconfig}"
echo "Downloading s3://operasds-dev-pge/${PGE_NAME}/${static_runconfig} to ${local_static_runconfig}"
aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/${static_runconfig} ${local_static_runconfig} --no-progress

# Pull in validation script from S3.
# Current source is https://raw.githubusercontent.com/opera-adt/COMPASS/main/src/compass/utils/validate_product.py
local_validate_script=${TMP_DIR}/validate_product.py
echo "Downloading s3://operasds-dev-pge/${PGE_NAME}/validate_cslc_product_calval_0.4.0.py to $local_validate_script"
aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/validate_cslc_product_calval_0.4.0.py "$local_validate_script" --no-progress

# overall_status values and their meanings
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

input_dir="${TMP_DIR}/${INPUT_DATA%.*}/input_data"
runconfig_dir="${TMP_DIR}/runconfig"

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

if [ $overall_status -eq 0 ]; then
    echo "<tr><th>Compare Result</th><th><ul><li>Expected file</li><li>Output file</li></ul></th><th>validate_product.py output</th></tr>" >> "$RESULTS_FILE"

    declare -a burst_ids=("t064_135518_iw1"
                          "t064_135519_iw1"
                          "t064_135520_iw1"
                          "t064_135521_iw1"
                          "t064_135522_iw1"
                          "t064_135523_iw1"
                          "t064_135524_iw1"
                          "t064_135525_iw1"
                          "t064_135526_iw1"
                          "t064_135527_iw1")

    for burst_id in "${burst_ids[@]}"; do
        cslc_compare_result="PENDING"
        expected_dir="${TMP_DIR}/${EXPECTED_DATA%.*}/expected_output_s1_cslc"

        echo "-------------------------------------"
        echo "Comparing results for burst id ${burst_id}"

        burst_id_uppercase=${burst_id^^}
        burst_id_replace_underscores=${burst_id_uppercase//_/-}
        burst_id_pattern="OPERA_L2_CSLC-S1_${burst_id_replace_underscores}_*.h5"
        output_file=`ls $output_dir/$burst_id_pattern`

        echo "Output CSLC file matching burst id is $output_file"

        ref_product="/exp/${burst_id}/20220501/${burst_id}_20220501.h5"
        sec_product="/out/$(basename ${output_file})"

        docker_out=$(docker run --rm -u compass_user:compass_user \
                                -v "${TMP_DIR}":/working:ro \
                                -v "${output_dir}":/out:ro \
                                -v "${expected_dir}":/exp:ro \
                                --entrypoint /home/compass_user/miniconda3/envs/COMPASS/bin/python3 \
                                ${PGE_IMAGE}:"${PGE_TAG}" \
                                /working/validate_product.py \
                                --ref-product ${ref_product} \
                                --sec-product ${sec_product} \
                                -p CSLC 2>&1) || docker_exit_status=$?

        echo "$docker_out"
        if [[ "$docker_out" != *"All CSLC product checks have passed"* ]]; then
            echo "Failure: All CSLC product checks DID NOT PASS"
            cslc_compare_result="FAIL"
            overall_status=2
        elif [[ "$docker_out" != *"All CSLC metadata checks have passed"* ]]; then
            echo "Failure: All CSLC metadata checks DID NOT PASS"
            cslc_compare_result="FAIL"
            overall_status=2
        else
            echo "Product validation was successful"
            cslc_compare_result="PASS"
        fi

        docker_out="${docker_out//$'\n'/<br>}"
        echo "<tr><td>${cslc_compare_result}</td><td><ul><li>${ref_product}</li><li>${sec_product}</li></ul></td><td>${docker_out}</td></tr>" >> "$RESULTS_FILE"

        static_layers_compare_result="PENDING"
        expected_dir="${TMP_DIR}/${EXPECTED_DATA%.*}/expected_output_s1_cslc_static"

        burst_id_pattern="OPERA_L2_CSLC-S1-STATIC_${burst_id_replace_underscores}_*.h5"
        output_file=`ls $static_output_dir/$burst_id_pattern`

        echo "Output static layers file matching burst id is $output_file"

        ref_product="/exp/${burst_id}/20220501/static_layers_${burst_id}.h5"
        sec_product="/out/$(basename ${output_file})"

        docker_out=$(docker run --rm -u compass_user:compass_user \
                                -v "${TMP_DIR}":/working:ro \
                                -v "${static_output_dir}":/out:ro \
                                -v "${expected_dir}":/exp:ro \
                                --entrypoint /home/compass_user/miniconda3/envs/COMPASS/bin/python3 \
                                ${PGE_IMAGE}:"${PGE_TAG}" \
                                /working/validate_product.py \
                                --ref-product ${ref_product} \
                                --sec-product ${sec_product} \
                                -p static_layers 2>&1) || docker_exit_status=$?

        echo "$docker_out"
        if [[ "$docker_out" != *"All CSLC product checks have passed"* ]]; then
            echo "Failure: All CSLC product checks DID NOT PASS"
            static_layers_compare_result="FAIL"
            overall_status=2
        elif [[ "$docker_out" != *"All CSLC metadata checks have passed"* ]]; then
            echo "Failure: All CSLC metadata checks DID NOT PASS"
            static_layers_compare_result="FAIL"
            overall_status=2
        else
            echo "Product validation was successful"
            static_layers_compare_result="PASS"
        fi

        docker_out="${docker_out//$'\n'/<br>}"
        echo "<tr><td>${static_layers_compare_result}</td><td><ul><li>${ref_product}</li><li>${sec_product}</li></ul></td><td>${docker_out}</td></tr>" >> "$RESULTS_FILE"
    done
fi
echo " "

if [ $overall_status -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi

exit $overall_status
