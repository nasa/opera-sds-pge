#!/bin/bash
# Script to execute integration tests on OPERA CSLC_S1 PGE Docker image
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
Integration Testing CSLC_S1 PGE docker image...
================================================
'

PGE_NAME="cslc_s1"
PGE_IMAGE="opera_pge/${PGE_NAME}"
SAMPLE_TIME=5

# defaults, test data and runconfig files should be updated as-needed to use
# the latest available as defaults for use with the Jenkins pipeline call
# TESTDATA should be the name of the test data archive in s3://operasds-dev-pge/cslc_s1/
# RUNCONFIG should be the name of the runconfig in s3://operasds-dev-pge/cslc_s1/
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath "$(dirname "$(realpath "$0")")"/../..)
[ -z "${PGE_TAG}" ] && PGE_TAG="${USER}-dev"
[ -z "${TESTDATA}" ] && TESTDATA="delivery_cslc_s1_interface_0.1.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="cslc_s1.yaml"

# Create the test output directory in the workspace
test_int_setup_results_directory

# Create a temporary directory to hold test data
test_int_setup_data_tmp_directory

# Download, extract and cd to test data directory
test_int_setup_test_data

# Setup cleanup on exit
trap test_int_trap_cleanup EXIT

# Pull in validation script from S3. This utility doesn't appear to be source-controlled
# so we have cached the delivery version in S3.
local_validate_cslc=${TMP_DIR}/validate_cslc.py
echo "Downloading s3://operasds-dev-pge/${PGE_NAME}/validate_cslc.py to $local_validate_cslc"
aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/validate_cslc.py "$local_validate_cslc"

# overall_status values and their meanings
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

# There is only 1 expected output directory for CSLC_S1
expected_dir="$(pwd)/expected_output"

# the testdata reference metadata contains this path so we use it here
output_dir="$(pwd)/output_rtc_s1"
# make sure no output directory already exists
if [ -d "$output_dir" ]; then
    echo "Output directory $output_dir already exists (and should not). Remove directory."
    rm -rf "${output_dir}"
fi
echo "Creating output directory $output_dir."
mkdir "$output_dir"

# the testdata reference metadata contains this path so we use it here
scratch_dir="$(pwd)/scratch_rtc_s1"
# make sure no scratch directory already exists
if [ -d "$scratch_dir" ]; then
    echo "Scratch directory $scratch_dir already exists (and should not). Remove directory."
    rm -rf "${scratch_dir}"
fi
echo "Creating scratch directory $scratch_dir."
mkdir "$scratch_dir"

container_name="${PGE_NAME}"

# Start metrics collection
metrics_collection_start "$PGE_NAME" "$container_name" "$TEST_RESULTS_DIR" "$SAMPLE_TIME"

echo "Running Docker image ${PGE_IMAGE}:${PGE_TAG}"

docker run --rm -u $UID:"$(id -g)" -w /home/compass_user --name $container_name \
           -v "$(pwd)":/home/compass_user/runconfig:ro \
           -v "$(pwd)"/input_data:/home/compass_user/input_data:ro \
           -v "${output_dir}":/home/compass_user/output_s1_cslc \
           -v "${scratch_dir}":/home/compass_user/scratch_s1_cslc \
           ${PGE_IMAGE}:"${PGE_TAG}" --file /home/compass_user/runconfig/"$RUNCONFIG_FILENAME"

docker_exit_status=$?

# End metrics collection
metrics_collection_end "$PGE_NAME" "$docker_exit_status" "$TEST_RESULTS_DIR"

if [ $docker_exit_status -ne 0 ]; then
    echo "docker exit indicates failure: ${docker_exit_status}"
    overall_status=1
else
    # Prepare to validate output products
    cp "$local_validate_cslc" .

    # Compare output files against expected files.
    # Note there are varying timestamp and product version in the product filenames.
    sec_product_file=$(ls -1 "${output_dir}"/OPERA_L2_CSLC-S1A_IW_T64-135524-IW2_VV_20220501T015052Z_*Z.tiff)
    sec_product=$(basename -- "${sec_product_file}")
    sec_metadata_file=$(ls -1 "${output_dir}"/OPERA_L2_CSLC-S1A_IW_T64-135524-IW2_VV_20220501T015052Z_*Z.json)
    sec_metadata=$(basename -- "${sec_metadata_file}")
    ref_product="t64_135524_iw2/20220501/t64_135524_iw2_20220501_VV.slc"
    ref_metadata="t64_135524_iw2/20220501/t64_135524_iw2_20220501_VV.json"

    if [ ! -f "${output_dir}"/"${sec_product}" ] || [ ! -f "${output_dir}"/"${sec_metadata}" ] ||
       [ ! -f "${expected_dir}"/${ref_product} ] || [ ! -f "${expected_dir}"/${ref_metadata} ]
    then
        echo "One or more output files or expected files are missing."
        ls "${output_dir}"/"${sec_product}"
        ls "${output_dir}"/"${sec_metadata}"
        ls "${expected_dir}"/${ref_product}
        ls "${expected_dir}"/${ref_metadata}
        overall_status=1
    else
        docker_out="N/A"
        compare_result="N/A"

        # Run validation script on output files
        docker_out=$(docker run --rm -u compass_user:compass_user \
                                -v "$(pwd)":/working:ro \
                                -v "${output_dir}":/out:ro \
                                -v "${expected_dir}":/exp:ro \
                                --entrypoint /home/compass_user/miniconda3/envs/COMPASS/bin/python3 \
                                ${PGE_IMAGE}:"${PGE_TAG}" \
                                /working/validate_cslc.py \
                                --ref-product /exp/"${ref_product}" \
                                --sec-product /out/"${sec_product}" \
                                --ref-metadata /exp/"${ref_metadata}" \
                                --sec-metadata /out/"${sec_metadata}")

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
        echo "<tr><td>${compare_result}</td><td><ul><li>${ref_product}</li><li>${sec_product}</li><li>${ref_metadata}</li><li>${sec_metadata}</li></ul></td><td>${docker_out}</td></tr>" >> "$RESULTS_FILE"
    fi
fi
echo " "

if [ $overall_status -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi

exit $overall_status
