#!/bin/bash
# Script to execute integration tests on OPERA DSWx-HLS PGE Docker image
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
Integration Testing DSWx-HLS PGE docker image...
================================================
'

PGE_NAME="dswx_hls"
PGE_IMAGE="opera_pge/${PGE_NAME}"
SAMPLE_TIME=5

# defaults, test data and runconfig files should be updated as-needed to use
# the latest available as defaults for use with the Jenkins pipeline call
# TESTDATA should be the name of the test data archive in s3://operasds-dev-pge/dswx_hls/
# RUNCONFIG should be the name of the runconfig in s3://operasds-dev-pge/dswx_hls/
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../..)
[ -z "${PGE_TAG}" ] && PGE_TAG="${USER}-dev"
[ -z "${TESTDATA}" ] && TESTDATA="delivery_cal_val_3.1.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="opera_pge_dswx_hls_delivery_3.1_cal_val_runconfig.yaml"

# Create the test output directory in the workspace
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

# For each <data_set> directory, run the Docker image to produce a <data_set>_output directory
# and then compare the contents of the output and expected directories
for data_set in l30_greenland s30_louisiana
do
    expected_dir="$(pwd)/${data_set}/expected_output_dir"
    data_dir=$(pwd)/${data_set}
    echo -e "\nTest data directory: ${data_dir}"

    # the testdata reference metadata contains this path so we use it here
    output_dir="$(pwd)/output_rtc_s1"
    # make sure no output directory already exists
    if [ -d "$output_dir" ]; then
        echo "Output directory $output_dir already exists (and should not). Exiting."
        exit 1
    fi

    echo "Creating output directory $output_dir."
    mkdir "$output_dir"

    # the testdata reference metadata contains this path so we use it here
    scratch_dir="$(pwd)/scratch_rtc_s1"
    # make sure no scratch directory already exists
    if [ -d "$scratch_dir" ]; then
        echo "Scratch directory $scratch_dir already exists (and should not). Exiting."
        exit 1
    fi
    echo "Creating scratch directory $scratch_dir."
    mkdir "$scratch_dir"

    container_name="${PGE_NAME}-${data_set}"

    # Start metrics collection
    metrics_collection_start "$PGE_NAME" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

    echo "Running Docker image ${PGE_IMAGE}:${PGE_TAG} for ${data_dir}"
    docker run --rm -u $UID:$(id -g) --name $container_name  \
                -v $(pwd):/home/conda/runconfig:ro \
                -v $data_dir/input_dir:/home/conda/input_dir:ro \
                -v $output_dir:/home/conda/output_dir \
                -v $scratch_dir:/home/conda/scratch_dir \
                ${PGE_IMAGE}:${PGE_TAG} --file /home/conda/runconfig/$RUNCONFIG_FILENAME

    docker_exit_status=$?

    # End metrics collection
    metrics_collection_end "$PGE_NAME" "$docker_exit_status" "$TEST_RESULTS_DIR"

    if [ $docker_exit_status -ne 0 ]; then
        echo "$data_dir docker exit indicates failure: ${docker_exit_status}"
        overall_status=1
    else
        # Compare output files against expected files
        for output_file in $output_dir/*
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
                for potential_product in B01_WTR B02_BWTR B03_CONF B04_DIAG B05_WTR-1 B06_WTR-2 B07_LAND B08_SHAD B09_CLOUD B10_DEM
                do
                    if [[ "$output_file" == *"$potential_product"* ]]; then
                        product=$potential_product
                        break
                    fi
                done

                echo "product is $product"

                for potential_file in $expected_dir/*.tif*
                do
                    if [[ "$potential_file" == *"$product"* ]]; then
                        echo "expected file is $potential_file"
                        expected_file=$potential_file
                        break
                    fi
                done

                if [ ! -f $expected_file ]; then
                    echo "No expected file found for product $product in expected directory $expected_dir"
                    overall_status=1
                else
                    # compare output and expected files
                    expected_file=$(basename -- "$expected_file")
                    docker_out=$(docker run --rm -u conda:conda \
                                            -v ${output_dir}:/out:ro \
                                            -v ${expected_dir}:/exp:ro \
                                            --entrypoint python3 ${PGE_IMAGE}:${PGE_TAG} \
                                            proteus-0.1/bin/dswx_compare.py \
                                            /out/${output_file} /exp/${expected_file})
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
            echo "<tr><td>${compare_result}</td><td><ul><li>Output: ${output_file}</li><li>Expected: ${expected_file}</li></ul></td><td>${docker_out}</td></tr>" >> $RESULTS_FILE
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
