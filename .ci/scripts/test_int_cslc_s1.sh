#!/bin/bash
# Script to execute integration tests on OPERA CSLC_S1 PGE Docker image
#

set -e

# Allow user group to remove created files.
umask 002

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      echo "Usage: test_int_cslc_S1.sh [-h|--help] [-t|--tag <tag>] [--testdata <testdata .zip file>] [--runconfig <runconfig .yaml file>]"
      exit 0
      ;;
    -t|--tag)
      TAG=$2
      shift
      shift
      ;;
    --testdata)
      TESTDATA=$2
      shift
      shift
      ;;
    --runconfig)
      RUNCONFIG=$2
      shift
      shift
      ;;
    -*|--*)
      echo "Unknown arguments $1 $2, ignoring..."
      shift
      shift
      ;;
    *)
      echo "Unknown argument $1, ignoring..."
      shift
      ;;
  esac
done

echo '
================================================
Integration Testing CSLC_S1 PGE docker image...
================================================
'

PGE_NAME="cslc_s1"
PGE_IMAGE="opera_pge/${PGE_NAME}"

TEST_RESULTS_REL_DIR="test_results"
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../..)
TEST_RESULTS_DIR="${WORKSPACE}/${TEST_RESULTS_REL_DIR}/${PGE_NAME}"

echo "Test results output directory: ${TEST_RESULTS_DIR}"
mkdir --parents ${TEST_RESULTS_DIR}
chmod -R 775 ${TEST_RESULTS_DIR}
RESULTS_FILE="${TEST_RESULTS_DIR}/test_int_${PGE_NAME}_results.html"

# For this version of integration test, an archive has been created which contains
# the unmodified ADT SAS test data archive and PGE expected output.

# TESTDATA should be the name of the test data archive in s3://operasds-dev-pge/cslc_s1/
# RUNCONFIG should be the name of the runconfig in s3://operasds-dev-pge/cslc_s1/

# Create a temporary directory to allow Jenkins to write to it and avoid collisions
# with other users
local_dir=$(mktemp -dp /tmp)
chmod 775 $local_dir
cd $local_dir

local_testdata_archive=${local_dir}/${TESTDATA}
local_runconfig=${local_dir}/${RUNCONFIG}

results_html_init="<html>${PGE_NAME} product comparison results<p> \
    <style>* {font-family: sans-serif;} \
    table {border-collapse: collapse;} \
    th,td {padding: 4px 6px; border: thin solid white} \
    tr:nth-child(even) {background-color: whitesmoke;} \
    </style><table>"

echo $results_html_init > $RESULTS_FILE

# Configure a trap to set permissions on exit regardless of whether the testing succeeds
function cleanup {

    echo "</table></html>" >> $RESULTS_FILE
    DOCKER_RUN="docker run --rm -u $UID:$(id -g)"

    echo "Cleaning up before exit. Setting permissions for output files and directories."
    ${DOCKER_RUN} -v ${local_dir}:${local_dir} --entrypoint /usr/bin/find ${PGE_IMAGE}:${TAG} ${local_dir} -type d -exec chmod 775 {} +
    ${DOCKER_RUN} -v ${local_dir}:${local_dir} --entrypoint /usr/bin/find ${PGE_IMAGE}:${TAG} ${local_dir} -type f -exec chmod 664 {} +
    rm -rf ${local_dir}
}

trap cleanup EXIT

# Pull in test data and runconfig from S3
echo "Downloading test data from s3://operasds-dev-pge/${PGE_NAME}/${TESTDATA} to $local_testdata_archive"
aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/${TESTDATA} $local_testdata_archive
echo "Downloading runconfig from s3://operasds-dev-pge/${PGE_NAME}/${RUNCONFIG} to $local_runconfig"
aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/${RUNCONFIG} $local_runconfig

# Pull in validation script from S3. This utility doesn't appear to be source-controlled
# so we have cached the delivery version in S3.
local_validate_cslc=${local_dir}/validate_cslc.py
echo "Downloading runconfig from s3://operasds-dev-pge/${PGE_NAME}/validate_cslc.py to $local_runconfig"
aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/validate_cslc.py $local_validate_cslc


# Extract the test data archive to the current directory
if [ -f $local_testdata_archive ]; then

    # The testdata archive should contain a directory with the same basename
    testdata_basename=$(basename -- "$local_testdata_archive")
    testdata_dir="${local_dir}/${testdata_basename%.*}"

    echo "Extracting test data from $local_testdata_archive to $(pwd)/"
    unzip $local_testdata_archive

    if [ -d $testdata_dir ]; then
        cd $testdata_dir
    else
        echo "The test data archive needs to include a directory named $testdata_dir, but it does not."
        exit 1
    fi
else
    echo "Unable to find test data file $local_testdata_archive"
    exit 1
fi

if [ -f $local_runconfig ]; then
    echo "Copying runconfig file $local_runconfig to $(pwd)/"
    cp $local_runconfig .

    runconfig_filename=$(basename -- "$local_runconfig")
else
    echo "Unable to find runconfig file $local_runconfig"
    exit 1
fi

# If any test case fails, this is set to non-zero
overall_status=0

# There is only 1 expected output directory for CSLC_S1
expected_dir="$(pwd)/expected_output"
data_dir=$(pwd)
echo -e "\nTest data directory: ${data_dir}"
output_dir="$(pwd)/pge_${PGE_NAME}_output"
echo "Checking if $output_dir exists (it shouldn't)."
if [ -d $output_dir ]; then
    echo "Output directory $output_dir already exists (and should not). Exiting."
    exit 1
fi
echo "Creating output directory $output_dir."
mkdir $output_dir
scratch_dir="$(pwd)/pge_${PGE_NAME}_scratch"
if [ -d $scratch_dir ]; then
    echo "Scratch directory $scratch_dir already exists (and should not). Exiting."
    exit 1
fi
echo "Creating scratch directory $scratch_dir."
mkdir $scratch_dir


echo "Running Docker image ${PGE_IMAGE}:${TAG} for ${data_dir}"
docker run --rm -u $UID:$(id -g) -v $(pwd):/home/conda/runconfig:ro \
           -v $data_dir/input_data:/home/conda/input_data:ro \
           -v $output_dir:/home/conda/output_dir \
           -v $scratch_dir:/home/conda/scratch_dir \
           ${PGE_IMAGE}:${TAG} --file /home/conda/runconfig/$runconfig_filename

docker_exit_status=$?
if [ $docker_exit_status -ne 0 ]; then
    echo "$data_dir docker exit indicates failure: ${docker_exit_status}"
    overall_status=1
else
    # Compare output files against expected files
    for output_file in $output_dir/*
    do
        echo "output_file $output_file"
        output_file=$(basename -- "$output_file")

        if [[ "${output_file##*/}" == *.slc ]]
        then
            echo "Output product is ${output_file}"
            sec_product=${output_file}
        elif [[ "${output_file##*/}" == *.json ]]
            echo "Output metadata is ${output_file}"
            sec_metadata=${output_file}
        else
            echo "Ignoring output file ${output_file}"
        fi
    done
    for expected_file in $expected_dir/*
    do
        echo "expected_file $expected_file"
        expected_file=$(basename -- "$expected_file")

        if [[ "${expected_file##*/}" == *.slc ]]
        then
            echo "Expected product is ${expected_file}"
            ref_product=${expected_file}
        elif [[ "${expected_file##*/}" == *.json ]]
            echo "Expected metadata is ${expected_file}"
            ref_metadata=${expected_file}
        else
            echo "Ignoring expected file ${expected_file}"
        fi
    done

    if [ -z sec_product ] || [ -z sec_metadata ] || [ -z ref_product ] || [ -z ref_metadata ]
    then
        echo "One or more output files or expected files are missing."
        overall_status=1
    else
        docker_out="N/A"
        compare_result="N/A"
        expected_file="N/A"
        # compare output and expected files
        expected_file=$(basename -- "$expected_file")
        docker_out=$(docker run --rm -u conda:conda \
                                -v ${output_dir}:/out:ro \
                                -v ${expected_dir}:/exp:ro \
                                --entrypoint python3 ${PGE_IMAGE}:${TAG} \
                                validate_cslc.py \
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

    echo "<tr><td>${compare_result}</td><td>Output: ${output_file}<br>Expected: ${expected_file}</td><td>${docker_out}</td></tr>" >> $RESULTS_FILE
echo " "
if [ $overall_status -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi

exit $overall_status
