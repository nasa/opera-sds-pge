#!/bin/bash
#
# test_int_util.sh
#
# Library of common shell routines for PGE integration testing.
#

# Base temp directory to use for file staging
DEFAULT_TMP_ROOT="/data/tmp"
# Associated with the --no-cleanup switch (default=<delete temp files on exit>)
DELETE_TEMP_FILES=true
# Associated with the --no-metrics switch (default=<collect metrics>)
COLLECT_METRICS=true

test_int_parse_args()
{
    # Parse command line arguments and set global variables to be used in calling script
    #
    while [[ $# -gt 0 ]]; do
    case $1 in
      -h|--help)
        echo "Usage: $(basename $0) [-h|--help] [-t|--tag <tag>] [-i|--input-data <zip file>] [-e|--expected-data <zip file>] [--runconfig <runconfig .yaml file>] [--no-metrics] [--no-cleanup] [--temp-root <path>]"
        exit 0
        ;;
      -t|--tag)
        PGE_TAG=$2
        shift
        shift
        ;;
      -i|--input-data)
        INPUT_DATA=$2
        shift
        shift
        ;;
      -e|--expected-data)
        EXPECTED_DATA=$2
        shift
        shift
        ;;
      --runconfig)
        RUNCONFIG=$2
        shift
        shift
        ;;
      --temp-root)
        TMP_ROOT=$2
        shift
        shift
        ;;
      --no-cleanup)
        DELETE_TEMP_FILES=false
        shift
        ;;
      --no-metrics)
        COLLECT_METRICS=false
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
    TMP_DIR=$(mktemp -dp ${TMP_ROOT})
    chmod 775 $TMP_DIR
}

test_int_setup_test_data()
{
    # Download test data and extract it
    #
    local_input_data_archive=${TMP_DIR}/${INPUT_DATA}
    local_expected_data_archive=${TMP_DIR}/${EXPECTED_DATA}
    local_runconfig=${TMP_DIR}/${RUNCONFIG}

    # Pull in test data and runconfig from S3
    echo "Downloading input data from s3://operasds-dev-pge/${PGE_NAME}/${INPUT_DATA} to $local_input_data_archive"
    aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/${INPUT_DATA} $local_input_data_archive --no-progress

    echo "Downloading expected outputs from s3://operasds-dev-pge/${PGE_NAME}/${EXPECTED_DATA} to $local_expected_data_archive"
    aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/${EXPECTED_DATA} $local_expected_data_archive --no-progress

    echo "Downloading runconfig from s3://operasds-dev-pge/${PGE_NAME}/${RUNCONFIG} to $local_runconfig"
    aws s3 cp s3://operasds-dev-pge/${PGE_NAME}/${RUNCONFIG} $local_runconfig --no-progress

    for local_testdata_archive in $local_input_data_archive $local_expected_data_archive
    do
        # Extract the test data archive to the current directory
        if [ -f $local_testdata_archive ]; then
            # The testdata archive should contain a directory with the same basename
            testdata_basename=$(basename -- "$local_testdata_archive")
            testdata_dir="${TMP_DIR}/${testdata_basename%.*}"

            echo "Extracting test data from $local_testdata_archive to ${TMP_DIR}/"
            unzip -qq $local_testdata_archive -d ${TMP_DIR}

            if [ -d $testdata_dir ]; then
                rm -f $local_testdata_archive
            else
                echo "The test data archive needs to include a directory named $testdata_dir, but it does not."
                exit 1
            fi
        else
            echo "Unable to find test data file $local_testdata_archive"
            exit 1
        fi
    done

    if [ -f $local_runconfig ]; then
        runconfig_dir="${TMP_DIR}/runconfig"
        mkdir --parents $runconfig_dir

        echo "Copying runconfig file $local_runconfig to $runconfig_dir/"
        cp $local_runconfig $runconfig_dir

        rm -f $local_runconfig
    else
        echo "Unable to find runconfig file $local_runconfig"
        exit 1
    fi
}

test_int_trap_cleanup_temp_dirs()
{
    # Finalize results HTML file and set permissions on data that was created during the test.

    echo "</table></html>" >> $RESULTS_FILE

    DOCKER_RUN="docker run --rm -u $UID:$(id -g)"

    # Check options before exiting
    if $DELETE_TEMP_FILES; then
        echo "Cleaning up before exit. Setting permissions for output files and directories."
        ${DOCKER_RUN} -v ${TMP_DIR}:${TMP_DIR} --entrypoint /usr/bin/find ${PGE_IMAGE}:${PGE_TAG} ${TMP_DIR} -type d -exec chmod 775 {} +
        ${DOCKER_RUN} -v ${TMP_DIR}:${TMP_DIR} --entrypoint /usr/bin/find ${PGE_IMAGE}:${PGE_TAG} ${TMP_DIR} -type f -exec chmod 664 {} +
        cd ${TMP_ROOT}
        rm -rf ${TMP_DIR}
    else
        echo "--no-cleanup flag set: Temporary directories will remain on disk."
    fi
}

test_int_trap_kill_metrics_pid()
{
    if $COLLECT_METRICS; then
        # End background metrics collection
        local stats_pid_file="${TEST_RESULTS_DIR}/${PGE_NAME}_metrics_stats_bg_pid.txt"
        if [ -e ${stats_pid_file} ]
        then
            process_to_kill=$(cat "${stats_pid_file}")
            if ps -p $process_to_kill > /dev/null
            then
                kill $process_to_kill
                wait $process_to_kill 2> /dev/null || true
            fi
            rm "${stats_pid_file}"
        fi
     else
         echo "--no-metrics flag set"
    fi
}

# Clean up functions that are called on EXIT from test_int_<PGE>.sh scripts
test_int_trap_cleanup()
{
  test_int_trap_cleanup_temp_dir
  test_int_trap_kill_metrics_pid
}
