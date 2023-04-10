#!/bin/bash
# Script to execute integration tests on OPERA DSWx-HLS PGE Docker image
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
Integration Testing DSWx-HLS PGE docker image...
================================================
'

PGE_NAME="dswx_hls"
PGE_IMAGE="opera_pge/${PGE_NAME}"
SAMPLE_TIME=15

# defaults, test data and runconfig files should be updated as-needed to use
# the latest available as defaults for use with the Jenkins pipeline call
# INPUT/OUTPUT_DATA should be the name of the corresponding archives in s3://operasds-dev-pge/dswx_hls/
# RUNCONFIG should be the name of the runconfig in s3://operasds-dev-pge/dswx_hls/
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath "$(dirname "$(realpath "$0")")"/../..)
[ -z "${PGE_TAG}" ] && PGE_TAG="${USER}-dev"
[ -z "${INPUT_DATA}" ] && INPUT_DATA="dswx_hls_final_4.1_expected_input.zip"
[ -z "${EXPECTED_DATA}" ] && EXPECTED_DATA="dswx_hls_final_4.1_expected_output.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="opera_pge_dswx_hls_delivery_4.1_final_runconfig.yaml"
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

# For each <data_set> directory, run the Docker image to produce a <data_set>/output_dir
# directory and then compare the contents of the output and expected directories
for data_set in l30_greenland s30_louisiana
do
    input_data_basename=$(basename -- "$INPUT_DATA")
    input_data_dir="${TMP_DIR}/${input_data_basename%.*}/${data_set}/input_dir"

    expected_data_basename=$(basename -- "$EXPECTED_DATA")
    expected_data_dir="${TMP_DIR}/${expected_data_basename%.*}/${data_set}/expected_output_dir"

    echo "Input data directory: ${input_data_dir}"
    echo "Expected data directory: ${expected_data_dir}"

    # the testdata reference metadata contains this path so we use it here
    output_dir="${TMP_DIR}/dswx_hls_output/${data_set}/output_dir"

    # make sure no output directory already exists
    if [ -d "$output_dir" ]; then
        echo "Output directory $output_dir already exists (and should not). Removing directory."
        rm -rf "${output_dir}"
    fi

    echo "Creating output directory $output_dir."
    mkdir -p "$output_dir"

    # the testdata reference metadata contains this path so we use it here
    scratch_dir="${TMP_DIR}/dswx_hls_scratch/${data_set}/scratch_dir"

    # make sure no scratch directory already exists
    if [ -d "$scratch_dir" ]; then
        echo "Scratch directory $scratch_dir already exists (and should not). Removing directory.."
        rm -rf "${scratch_dir}"
    fi
    echo "Creating scratch directory $scratch_dir."
    mkdir -p --mode=777 "$scratch_dir"

    # Assign a container name to avoid the auto-generated one created by Docker
    container_name="${PGE_NAME}-${data_set}"

    # Start metrics collection
    metrics_collection_start "$PGE_NAME" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

    echo "Running Docker image ${PGE_IMAGE}:${PGE_TAG} for ${input_data_dir}"
    docker run --rm -u $UID:"$(id -g)" --name $container_name \
                -v "${TMP_DIR}/runconfig":/home/conda/runconfig:ro \
                -v "$input_data_dir":/home/conda/input_dir:ro \
                -v "$output_dir":/home/conda/output_dir \
                -v "$scratch_dir":/home/conda/scratch_dir \
                ${PGE_IMAGE}:"${PGE_TAG}" --file /home/conda/runconfig/"$RUNCONFIG"

    docker_exit_status=$?

    # End metrics collection
    metrics_collection_end "$PGE_NAME" "$container_name" "$docker_exit_status" "$TEST_RESULTS_DIR"

    if [ $docker_exit_status -ne 0 ]; then
        echo "docker exit indicates failure: ${docker_exit_status}"
        overall_status=1
    else
        # Compare output files against expected files
        for output_file in "$output_dir"/*
        do
            docker_out="N/A"
            compare_result="N/A"
            expected_file="N/A"

            echo "output_file $output_file"
            output_file=$(basename -- "$output_file")

            if [[ "${output_file##*/}" == *.log ]]
            then
                echo "Not comparing log file ${output_file}"
                compare_result="SKIPPED"

            elif [[ "${output_file##*/}" == *.tif* ]]
            then
                for potential_product in B01_WTR B02_BWTR B03_CONF B04_DIAG B05_WTR-1 B06_WTR-2 B07_LAND B08_SHAD B09_CLOUD B10_DEM BROWSE
                do
                    if [[ "$output_file" == *"$potential_product"* ]]; then
                        product=$potential_product
                        break
                    fi
                done

                echo "product is $product"

                for potential_file in "$expected_data_dir"/*.tif*
                do
                    if [[ "$potential_file" == *"$product"* ]]; then
                        echo "expected file is $potential_file"
                        expected_file=$potential_file
                        break
                    fi
                done

                if [ ! -f "$expected_file" ]; then
                    echo "No expected file found for product $product in expected directory $expected_data_dir"
                    overall_status=1
                else
                    # compare output and expected files
                    expected_file=$(basename -- "$expected_file")
                    docker_out=$(docker run --rm -u conda:conda \
                                     -v "${output_dir}":/out:ro \
                                     -v "${expected_data_dir}":/exp:ro \
                                     -v "$SCRIPT_DIR":/scripts \
                                     --entrypoint python3 ${PGE_IMAGE}:"${PGE_TAG}" \
                                     /scripts/dswx_compare_opera_pge.py \
                                     /out/"${output_file}" /exp/"${expected_file}" --metadata_exclude_list PRODUCT_VERSION)
                    echo "$docker_out"

                    if [[ "$docker_out" == *"[FAIL]"* ]]; then
                        echo "File comparison failed. Output and expected files differ for ${output_file}"
                        compare_result="FAIL"
                        overall_status=2
                    elif [[ "$docker_out" == *"ERROR"* ]]; then
                        echo "An error occurred during file comparison."
                        compare_result="ERROR"
                        overall_status=1
                    else
                        echo "File comparison passed for ${output_file}"
                        compare_result="PASS"
                    fi
                fi
            else
                echo "Not comparing file ${output_file}"
                compare_result="SKIPPED"
            fi

            docker_out="${docker_out//$'\n'/<br>}"
            echo "<tr><td>${compare_result}</td><td><ul><li>Output: ${output_file}</li><li>Expected: ${expected_file}</li></ul></td><td>${docker_out}</td></tr>" >> "$RESULTS_FILE"
        done
    fi
done
echo " "
if [ $overall_status -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi

exit $overall_status
