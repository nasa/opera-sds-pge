#!/bin/bash
# Script to execute integration tests on OPERA DISP-NI PGE Docker image
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
Integration Testing DISP-NI PGE docker image...
================================================
'

PGE_NAME="disp_ni"
PGE_IMAGE="opera_pge/${PGE_NAME}"
SAMPLE_TIME=15

# defaults, test data and runconfig files should be updated as-needed to use
# the latest available as defaults for use with the Jenkins pipeline call
# INPUT/OUTPUT_DATA should be the name of the corresponding archives in s3://operasds-dev-pge/disp_ni/
# RUNCONFIG should be the name of the runconfig in s3://operasds-dev-pge/disp_ni/
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath "$(dirname "$(realpath "$0")")"/../../..)
[ -z "${PGE_TAG}" ] && PGE_TAG="${USER}-dev"
[ -z "${INPUT_DATA}" ] && INPUT_DATA="disp_ni_gamma_0.3.1_expected_input.zip"
[ -z "${EXPECTED_DATA}" ] && EXPECTED_DATA="disp_ni_gamma_0.3.1_expected_output.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="opera_pge_disp_ni_r3.1_gamma_runconfig_forward.yaml"
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

echo "Testing DISP-NI Baseline Workflow(s)"

input_dir="${TMP_DIR}/${INPUT_DATA%.*}/input_dir"
runconfig_dir="${TMP_DIR}/runconfig"

expected_data_dir="${TMP_DIR}/${EXPECTED_DATA%.*}/expected_output"

echo "Input data directory: ${input_dir}"
echo "Expected data directory: ${expected_data_dir}"

# Run integration tests for DISP-NI in both "forward" and "historical" modes
for mode in forward historical
do
  for ionosphere_mode in A B
  do
    output_dir="${TMP_DIR}/output_disp_ni/${mode}_option${ionosphere_mode}"

    # make sure no output directory already exists
    if [ -d "$output_dir" ]; then
        echo "Output directory $output_dir already exists (and should not). Removing directory."
        rm -rf "${output_dir}"
    fi

    echo "Creating output directory $output_dir."
    mkdir -p "$output_dir"

    scratch_dir="${TMP_DIR}/scratch_disp_ni/${mode}_option${ionosphere_mode}"

    # make sure no scratch directory already exists
    if [ -d "$scratch_dir" ]; then
        echo "Scratch directory $scratch_dir already exists (and should not). Removing directory."
        rm -rf "${scratch_dir}"
    fi
    echo "Creating scratch directory $scratch_dir."
    mkdir -p --mode=777 "$scratch_dir"

    # Copy the RunConfig
    runconfig="opera_pge_disp_ni_r3.1_gamma_runconfig_${mode}_option${ionosphere_mode}.yaml"
    local_runconfig="${SCRIPT_DIR}/${runconfig}"
    echo "Copying runconfig file $local_runconfig to $runconfig_dir"
    cp ${local_runconfig} ${runconfig_dir}

    # Copy the Algorithm Parameters RunConfigs
    algo_runconfig="opera_pge_disp_ni_r3.1_gamma_algorithm_parameters_${mode}.yaml"
    local_algo_runconfig="${SCRIPT_DIR}/${algo_runconfig}"
    echo "Copying runconfig file $local_algo_runconfig to $runconfig_dir"
    cp ${local_algo_runconfig} ${runconfig_dir}

    # Copy the Iono Algorithm Parameters RunConfigs
    iono_algo_runconfig="opera_pge_disp_ni_r3.1_gamma_algorithm_parameters_ionosphere_${mode}.yaml"
    local_iono_algo_runconfig="${SCRIPT_DIR}/${iono_algo_runconfig}"
    echo "Copying runconfig file $local_iono_algo_runconfig to $runconfig_dir"
    cp ${local_iono_algo_runconfig} ${runconfig_dir}

    container_name="${PGE_NAME}-${mode}-option${ionosphere_mode}-PID$$"

    # Start metrics collection
    metrics_collection_start "$PGE_NAME" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

    echo "Running Docker image ${PGE_IMAGE}:${PGE_TAG} for ${mode} mode with ionospheric delay estimation method ${ionosphere_mode}"
    docker run --rm -u $UID:"$(id -g)" --name $container_name \
               -w /home/mamba \
               -v ${runconfig_dir}:/home/mamba/runconfig \
               -v ${input_dir}:/home/mamba/input_dir \
               -v ${output_dir}:/home/mamba/output_dir \
               -v ${scratch_dir}:/home/mamba/scratch_dir \
               -v ${expected_data_dir}/${mode}:/home/mamba/expected_output_dir \
               ${PGE_IMAGE}:"${PGE_TAG}" --file /home/mamba/runconfig/opera_pge_disp_ni_r3.1_gamma_runconfig_${mode}_option${ionosphere_mode}.yaml

    docker_exit_status=$?

    # End metrics collection
    metrics_collection_end "$PGE_NAME" "$container_name" "$docker_exit_status" "$TEST_RESULTS_DIR"

    # Copy the PGE/SAS log file(s) to the test results directory so it can be archived
    # by Jenkins with the other results
    cp "${output_dir}"/*.log "${TEST_RESULTS_DIR}"

    # Copy the results.html file to the same directory
    cp "${output_dir}"/test_int_disp_ni_results.html "${TEST_RESULTS_DIR}"/test_int_disp_ni_${mode}_option${ionosphere_mode}_results.html

    if [ $docker_exit_status -ne 0 ]; then
        echo "docker exit indicates failure: ${docker_exit_status}"
        overall_status=1
    else
        # Retrieve the return code written to disk by the comparison script
        test_status=$(cat "$output_dir/compare_disp_ni_products.rc")

        if [ $test_status -ne 0 ]; then
          overall_status=$test_status
        fi
    fi
  done
done

if [ $overall_status -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi

exit $overall_status
