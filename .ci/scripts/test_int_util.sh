#!/bin/bash
#
# test_int_util.sh
#
# Library of common shell routines for PGE integration testing.
#
set -e
umask 002

[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../..)

test_int_parse_args()
{
    # Parse command line arguments and set global variables to be used in calling script
    #
    while [[ $# -gt 0 ]]; do
    case $1 in
      -h|--help)
        echo "Usage: $(basename $0) [-h|--help] [-t|--tag <tag>] [--testdata <testdata .zip file>] [--runconfig <runconfig .yaml file>]"
        exit 0
        ;;
      -t|--tag)
        PGE_TAG=$2
        echo "PGE_TAG is $PGE_TAG"
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
}

test_int_setup_results_directory()
{
    # Create the test_results directory for the PGE and initialize the HTML output file.
    #
    TEST_RESULTS_DIR="${WORKSPACE}/test_results/${PGE_NAME}"

    echo "Test results output directory: ${TEST_RESULTS_DIR}"
    mkdir --parents ${TEST_RESULTS_DIR}
    chmod -R 775 ${TEST_RESULTS_DIR}
    RESULTS_FILE="${TEST_RESULTS_DIR}/test_int_${PGE_NAME}_results.html"

    # Add the initial HTML to the results file
    results_html_init="<html><b>${PGE_NAME} product comparison results</b><p> \
        <style>* {font-family: sans-serif;} \
        table {border-collapse: collapse;} \
        th,td {padding: 4px 6px; border: thin solid white} \
        tr:nth-child(even) {background-color: whitesmoke;} \
        </style><table>"
    echo "${results_html_init}" > ${RESULTS_FILE}
}

test_int_setup_data_tmp_directory()
{
    # Create a temporary directory to allow Jenkins to write to it and avoid collisions
    # with other users
    TMP_DIR=$(mktemp -dp /data/tmp)
    chmod 775 $TMP_DIR
    cd $TMP_DIR
}

test_int_setup_test_data()
{
    # Download test data and extract it
    #
    local_testdata_archive=${TMP_DIR}/${TESTDATA}
    local_runconfig=${TMP_DIR}/${RUNCONFIG}

    # Pull in test data and runconfig from S3
    echo "Downloading test data from s3://operasds-dev-pge/${PGE_NAME}/${TESTDATA} to $local_testdata_archive"
    aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/${TESTDATA} $local_testdata_archive
    echo "Downloading runconfig from s3://operasds-dev-pge/${PGE_NAME}/${RUNCONFIG} to $local_runconfig"
    aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/${RUNCONFIG} $local_runconfig

    cd ${TMP_DIR}

    # Extract the test data archive to the current directory
    if [ -f $local_testdata_archive ]; then

        # The testdata archive should contain a directory with the same basename
        testdata_basename=$(basename -- "$local_testdata_archive")
        testdata_dir="${TMP_DIR}/${testdata_basename%.*}"

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

        RUNCONFIG_FILENAME=$(basename -- "$local_runconfig")
    else
        echo "Unable to find runconfig file $local_runconfig"
        exit 1
    fi
}

test_int_trap_cleanup()
{
    # Finalize results HTML file and set permissions on data that was created during the test.
    #
    echo "</table></html>" >> $RESULTS_FILE

    DOCKER_RUN="docker run --rm -u $UID:$(id -g)"

    echo "Cleaning up before exit. Setting permissions for output files and directories."
    ${DOCKER_RUN} -v ${TMP_DIR}:${TMP_DIR} --entrypoint /usr/bin/find ${PGE_IMAGE}:${PGE_TAG} ${TMP_DIR} -type d -exec chmod 775 {} +
    ${DOCKER_RUN} -v ${TMP_DIR}:${TMP_DIR} --entrypoint /usr/bin/find ${PGE_IMAGE}:${PGE_TAG} ${TMP_DIR} -type f -exec chmod 664 {} +
    cd /data/tmp
    rm -rf ${TMP_DIR}
}
