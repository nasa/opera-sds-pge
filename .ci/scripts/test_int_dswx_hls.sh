#!/bin/bash
# Script to execute integration tests on OPERA DSWx-HLS PGE Docker image
#

set -e

# Allow user group to remove created files.
umask 002

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      echo "Usage: test_int_dswx_hls.sh [-h|--help] [-t|--tag <tag>] [--testdata <testdata .zip file>] [--runconfig <runconfig .yaml file>]"
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
Integration Testing DSWx-HLS PGE docker image...
================================================
'

PGE_NAME="dswx_hls"
PGE_IMAGE="opera_pge/${PGE_NAME}"
TEST_RESULTS_REL_DIR="test_results"

# defaults, test data and runconfig files should be updated as-needed to use
# the latest available as defaults for use with the Jenkins pipeline call
# TESTDATA should be the name of the test data archive in s3://operasds-dev-pge/dswx_hls/
# RUNCONFIG should be the name of the runconfig in s3://operasds-dev-pge/dswx_hls/
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../..)
[ -z "${TESTDATA}" ] && TESTDATA="delivery_3_cal_val.zip"
[ -z "${RUNCONFIG}" ] && RUNCONFIG="opera_pge_dswx_hls_delivery_3.0_cal_val_runconfig.yaml"

TEST_RESULTS_DIR="${WORKSPACE}/${TEST_RESULTS_REL_DIR}/${PGE_NAME}"

echo "Test results output directory: ${TEST_RESULTS_DIR}"
mkdir --parents ${TEST_RESULTS_DIR}
chmod -R 775 ${TEST_RESULTS_DIR}
RESULTS_FILE="${TEST_RESULTS_DIR}/test_int_${PGE_NAME}_results.html"

# For this version of integration test, an archive has been created which contains
# the unmodified ADT SAS test data archive and PGE expected output.

# Create a temporary directory to allow Jenkins to write to it and avoid collisions
# with other users
local_dir=$(mktemp -dp /tmp)
chmod 775 $local_dir
cd $local_dir

local_testdata_archive=${local_dir}/${TESTDATA}
local_runconfig=${local_dir}/${RUNCONFIG}

results_html_init="<html><b>${PGE_NAME} product comparison results</b><p> \
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
    cd /tmp
    rm -rf ${local_dir}
}

trap cleanup EXIT

# Pull in test data and runconfig from S3
echo "Downloading test data from s3://operasds-dev-pge/${PGE_NAME}/${TESTDATA} to $local_testdata_archive"
aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/${TESTDATA} $local_testdata_archive
echo "Downloading runconfig from s3://operasds-dev-pge/${PGE_NAME}/${RUNCONFIG} to $local_runconfig"
aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/${RUNCONFIG} $local_runconfig

# Extract the test data archive to the current directory
if [ -f $local_testdata_archive ]; then

    # The testdata archive should contain a directory with the same basename
    testdata_basename=$(basename -- "$local_testdata_archive")
    testdata_dir="${local_dir}/${testdata_basename%.*}"

    echo "Extracting test data from $local_testdata_archive to $(pwd)/"
    unzip $local_testdata_archive

    if [ -d $testdata_dir ]; then
        rm $local_testdata_archive
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
    output_dir="$(pwd)/${data_set}_output"
    echo "Checking if $output_dir exists (it shouldn't)."
    if [ -d $output_dir ]; then
        echo "Output directory $output_dir already exists (and should not). Exiting."
        exit 1
    fi
    echo "Creating output directory $output_dir."
    mkdir $output_dir
    scratch_dir="$(pwd)/${data_set}_scratch"
    if [ -d $scratch_dir ]; then
        echo "Scratch directory $scratch_dir already exists (and should not). Exiting."
        exit 1
    fi
    echo "Creating scratch directory $scratch_dir."
    mkdir $scratch_dir


    echo "Running Docker image ${PGE_IMAGE}:${TAG} for ${data_dir}"
    docker run --rm -u $UID:$(id -g) -v $(pwd):/home/conda/runconfig:ro \
                     -v $data_dir/input_dir:/home/conda/input_dir:ro \
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
                for potential_product in B01_WTR B02_BWTR B03_CONF B04_DIAG B05_WTR-1 B06_WTR-2 B08_SHAD B09_CLOUD B10_DEM
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
                                            --entrypoint python3 ${PGE_IMAGE}:${TAG} \
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

            echo "<tr><td>${compare_result}</td><td>Output: ${output_file}<br>Expected: ${expected_file}</td><td>${docker_out}</td></tr>" >> $RESULTS_FILE
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
