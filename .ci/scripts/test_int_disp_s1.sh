#!/bin/bash
# Script to execute integration tests on OPERA DISP-S1 PGE Docker image
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
Integration Testing DISP-S1 PGE docker image...
================================================
'

PGE_NAME="disp_s1"
PGE_IMAGE="opera_pge/${PGE_NAME}"
SAMPLE_TIME=2

# defaults, test data and runconfig files should be updated as-needed to use
# the latest available as defaults for use with the Jenkins pipeline call
# INPUT/OUTPUT_DATA should be the name of the corresponding archives in s3://operasds-dev-pge/disp_s1/
# RUNCONFIG should be the name of the runconfig in s3://operasds-dev-pge/disp_s1/
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath "$(dirname "$(realpath "$0")")"/../..)
[ -z "${PGE_TAG}" ] && PGE_TAG="${USER}-dev"
[ -z "${INPUT_DATA}" ] && INPUT_DATA="disp_s1_r2.1_interface_expected_input.zip"
[ -z "${EXPECTED_DATA}" ] && EXPECTED_DATA="disp_s1_r2.1_interface_expected_output.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="opera_pge_disp_s1_r2.1_interface_runconfig.yaml"
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

# There is only 1 expected output directory for DISP-S1
expected_dir="${TMP_DIR}/${EXPECTED_DATA%.*}/golden_output"
input_dir="${TMP_DIR}/${INPUT_DATA%.*}"
runconfig_dir="${TMP_DIR}/runconfig"

# the testdata reference metadata contains this path so we use it here
output_dir="${TMP_DIR}/output_disp_s1"

# make sure no output directory already exists
if [ -d "$output_dir" ]; then
    echo "Output directory $output_dir already exists (and should not). Removing directory."
    rm -rf "${output_dir}"
fi
echo "Creating output directory $output_dir."
mkdir -p "$output_dir"

# the testdata reference metadata contains this path so we use it here
scratch_dir="${TMP_DIR}/scratch_disp_s1"

# make sure no scratch directory already exists
if [ -d "$scratch_dir" ]; then
    echo "Scratch directory $scratch_dir already exists (and should not). Removing directory."
    rm -rf "${scratch_dir}"
fi
echo "Creating scratch directory $scratch_dir."
mkdir -p --mode=777 "$scratch_dir"

container_name="${PGE_NAME}-PID$$"

# Start metrics collection
metrics_collection_start "$PGE_NAME" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

echo "Running Docker image ${PGE_IMAGE}:${PGE_TAG}"

docker run --rm -u $UID:"$(id -g)" --name $container_name \
           -v ${runconfig_dir}:/home/mamba/runconfig \
           -v ${input_dir}:/home/mamba/input_dir \
           -v ${output_dir}:/home/mamba/output_dir \
           -v ${scratch_dir}:/home/mamba/scratch_dir \
           ${PGE_IMAGE}:"${PGE_TAG}" --file /home/mamba/runconfig/"$RUNCONFIG"

docker_exit_status=$?

# End metrics collection
metrics_collection_end "$PGE_NAME" "$container_name" "$docker_exit_status" "$TEST_RESULTS_DIR"

# Copy the PGE/SAS log file(s) to the test results directory so it can be archived
# by Jenkins with the other results
cp "${output_dir}"/*.log "${TEST_RESULTS_DIR}"

if [ $docker_exit_status -ne 0 ]; then
    echo "docker exit indicates failure: ${docker_exit_status}"
    overall_status=1
else
    echo "<tr><th>Compare Result</th><th><ul><li>Expected file</li><li>Output file</li></ul></th><th>disp_validate_product_opera_pge.py output</th></tr>" >> "$RESULTS_FILE"

    output_file="20180101_20180330.unw.nc"
    expected_file="20180101_20180330.unw.nc"

    docker_out=$(docker run --rm \
                            -v "${output_dir}":/out:ro \
                            -v "${expected_dir}":/exp:ro \
                            -v "$SCRIPT_DIR":/scripts \
                            --entrypoint /opt/conda/bin/python ${PGE_IMAGE}:"${PGE_TAG}" \
                            /scripts/disp_validate_product_opera_pge.py \
                            /out/${output_file} /exp/${expected_file} \
                            --exclude_groups pge_runconfig)
    echo "$docker_out"

    if [[ "$docker_out" == *"ERROR"* ]]; then
        echo "File comparison failed. Output and expected files differ for ${output_file}"
        compare_result="FAIL"
        overall_status=2
    else
        echo "File comparison passed for ${output_file}"
        compare_result="PASS"
    fi

    docker_out="${docker_out//$'\n'/<br>}"
    echo "<tr><td>${compare_result}</td><td><ul><li>Expected: ${expected_file}</li><li>Output: ${output_file}</li></ul></td><td>${docker_out}</td></tr>" >> "$RESULTS_FILE"
fi

echo " "
if [ $overall_status -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi

exit $overall_status
