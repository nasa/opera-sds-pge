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
      echo "Usage: test_int_dswx_hls.sh [-h|--help] [-t|--tag <tag>] [--testdata <testdata .tgz file>] [--runconfig <runconfig .yaml file>]"
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

# For this version of integration test, an archive has been created which contains
# the unmodified ADT SAS test data archive and PGE expected output.

# TESTDATA should be the name of the test data archive.
# Execution will take place in the current directory.

# Extract the test data archive to the current directory
if [ -f $TESTDATA ]; then
    echo "Extracting test data from $TESTDATA to current directory."
    tar xfz $TESTDATA

    # cd into the extracted directory which must be named to match the archive file
    filename=$(basename -- "$TESTDATA")
    filename="${filename%.*}"
    cd $filename
else
    echo "Unable to find test data file $TESTDATA"
    exit 1
fi

if [ -f $RUNCONFIG ]; then
    echo "Copying runconfig file $RUNCONFIG to current directory."
    cp $RUNCONFIG .

    RUNCONFIG_FILENAME=$(basename -- "$RUNCONFIG")
else
    echo "Unable to find runconfig file $RUNCONFIG"
    exit 1
fi

# If any test case fails, this is set to non-zero
OVERALL_STATUS=0

# For each <data_dir>_expected directory, run the Docker image to produce a <data_dir>_output directory
# and then compare the contents of the output and expected directories
for EXPECTED_DIR in *_expected/
do
    EXPECTED_DIR=${EXPECTED_DIR%/}
    DATA_DIR=${EXPECTED_DIR%_expected}
    echo -e "\nTest data directory: ${DATA_DIR}"
    OUTPUT_DIR="${DATA_DIR}_output"
    echo "Checking if $OUTPUT_DIR exists (it shouldn't)."
    if [ -d $OUTPUT_DIR ]; then
        echo "Output directory $OUTPUT_DIR already exists (and should not). Exiting."
        exit 1
    fi

    echo "Creating output directory $OUTPUT_DIR."
    mkdir $OUTPUT_DIR
    echo "Running Docker image ${PGE_IMAGE}:${TAG} for ${DATA_DIR}"
    docker run --rm -u $UID:$(id -g) -v $(pwd):/home/conda/runconfig:ro \
                     -v $(pwd)/${DATA_DIR}/input_dir:/home/conda/input_dir:ro \
                     -v $(pwd)/$OUTPUT_DIR:/home/conda/output_dir -i --tty \
                     ${PGE_IMAGE}:${TAG} --file /home/conda/runconfig/$RUNCONFIG_FILENAME

    docker_exit_status=$?
    if [ $docker_exit_status -ne 0 ]; then
        echo "$DATA_DIR docker exit indicates failure: ${docker_exit_status}"
        OVERALL_STATUS=1
    else
        # Compare output files against expected files
        for output_file in $OUTPUT_DIR/*
        do
            echo " "
            output_file=$(basename -- "$output_file")
            if [ -f "${EXPECTED_DIR}/${output_file##*/}" ]; then
                echo "Output:   ${OUTPUT_DIR}/${output_file}"
                echo "Expected: ${EXPECTED_DIR}/${output_file}"

                if [[ "${output_file##*/}" == *.log ]]
                then
                    echo "Not comparing log file ${output_file}"

                elif [[ "${output_file##*/}" == *.tif* ]]
                then
                    docker_out=$(docker run --rm -u conda:conda \
                                            -v $(pwd)/${OUTPUT_DIR}:/out:ro \
                                            -v $(pwd)/${EXPECTED_DIR}:/exp:ro \
                                            --entrypoint python3 ${PGE_IMAGE}:${TAG} \
                                            proteus-0.1/bin/dswx_compare.py \
                                            /out/${output_file} /exp/${output_file})
                    echo "$docker_out"
                    if [[ "$docker_out" == *"[FAIL]"* ]]; then
                        echo "File comparison failed. Output and expected files differ for ${output_file}"
                        OVERALL_STATUS=1
                    else
                        echo "File comparison passed for ${output_file}"
                    fi
                else
                    echo "Not comparing file ${output_file}"
                fi
            else
                echo "Test failed; expected file doesn't exist for output file ${output_file}."
                OVERALL_STATUS=1
            fi
        done
    fi
done
echo " "
if [ $OVERALL_STATUS -ne 0 ]; then
    echo "Test FAILED."
else
    echo "Test PASSED."
fi
exit $OVERALL_STATUS
