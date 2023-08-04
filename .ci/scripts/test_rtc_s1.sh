#!/bin/bash
# Script to execute unit tests on the OPERA RTC-S1 PGE Docker image

set -e

# Source the build script utility functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

. "${SCRIPT_DIR}"/util.sh

# Parse args
parse_build_args "$@"

echo '
=====================================

Testing RTC-S1 PGE Docker image...

=====================================
'

PGE_NAME="rtc_s1"
IMAGE="opera_pge/${PGE_NAME}"
TEST_RESULTS_REL_DIR="test_results"
CONTAINER_HOME="/home/rtc_user"
CONDA_ROOT="/home/rtc_user/miniconda3"

# defaults
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../..)
[ -z "${TAG}" ] && TAG="${USER}-dev"

TEST_RESULTS_DIR="${WORKSPACE}/${TEST_RESULTS_REL_DIR}/${PGE_NAME}"

echo "Test results output directory: ${TEST_RESULTS_DIR}"
mkdir --parents ${TEST_RESULTS_DIR}
chmod -R 775 ${WORKSPACE}/${TEST_RESULTS_REL_DIR}

# Use the environment of the docker image to run linting, tests, etc...
# Note the change of working directory (-w) to a directory without
# Python code so that import statements favor Python code found in the
# Docker image rather than code found on the host.
DOCKER_RUN="docker run --rm \
    -v ${WORKSPACE}:/workspace \
    -v ${WORKSPACE}/src/opera/test/data:${CONTAINER_HOME}/opera/test/data \
    -w /workspace/${TEST_RESULTS_REL_DIR} \
    -u ${UID}:$(id -g) \
    --entrypoint conda \
    ${IMAGE}:${TAG}"

ENTRYPOINT="run --no-capture-output -n RTC ${CONDA_ROOT}/bin/pge_tests_entrypoint.sh"

# Configure a trap to set permissions on exit regardless of whether the testing succeeds
function set_perms {
    # Open up permissions on all test results so we can be sure the CI system can
    # delete them after results are archived within Jenkins
    ${DOCKER_RUN} ${ENTRYPOINT} bash -c "find \
        /workspace/${TEST_RESULTS_REL_DIR} -type d -exec chmod 775 {} +"

    ${DOCKER_RUN} ${ENTRYPOINT} bash -c "find \
        /workspace/${TEST_RESULTS_REL_DIR} -type f -exec chmod 664 {} +"
}

trap set_perms EXIT

# linting and pep8 style check (configured by .flake8 and .pylintrc)
${DOCKER_RUN} ${ENTRYPOINT} flake8 \
    --config ${CONTAINER_HOME}/opera/.flake8 \
    --jobs auto \
    --exit-zero \
    --application-import-names opera \
    --output-file /workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/flake8.log \
    ${CONTAINER_HOME}/opera

${DOCKER_RUN} ${ENTRYPOINT} pylint \
    --rcfile=${CONTAINER_HOME}/opera/.pylintrc \
    --jobs 0 \
    --exit-zero \
    --output=/workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/pylint.log \
    --enable-all-extensions \
    ${CONTAINER_HOME}/opera

# pytest (including code coverage)
${DOCKER_RUN} ${ENTRYPOINT} pytest \
    --junit-xml=/workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/pytest-junit.xml \
    --cov=${CONTAINER_HOME}/opera/pge/base \
    --cov=${CONTAINER_HOME}/opera/pge/${PGE_NAME} \
    --cov=${CONTAINER_HOME}/opera/scripts \
    --cov=${CONTAINER_HOME}/opera/util \
    --cov-report=term \
    --cov-report=html:/workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/coverage_html \
    /workspace/src/opera/test/pge/base \
    /workspace/src/opera/test/pge/${PGE_NAME} \
    /workspace/src/opera/test/scripts \
    /workspace/src/opera/test/util > ${TEST_RESULTS_DIR}/pytest.log

echo "RTC-S1 PGE Docker image test complete"

exit 0
