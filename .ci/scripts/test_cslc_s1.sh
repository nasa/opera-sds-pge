#!/bin/bash
# Script to execute unit tests on the OPERA CSLC-S1 PGE Docker image

set -e

# Source the build script utility functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

. "${SCRIPT_DIR}"/util.sh

# Parse args
parse_build_args "$@"

echo '
=====================================

Testing CSLC-S1 PGE Docker image...

=====================================
'

PGE_NAME="cslc_s1"
IMAGE="opera_pge/${PGE_NAME}"
TEST_RESULTS_REL_DIR="test_results"
CONTAINER_HOME="/home/compass_user"
CONDA_ROOT="/home/compass_user/miniconda3"

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
    --entrypoint ${CONDA_ROOT}/bin/pge_tests_entrypoint.sh \
    ${IMAGE}:${TAG}"

# Configure a trap to set permissions on exit regardless of whether the testing succeeds
function set_perms {
    # Open up permissions on all test results so we can be sure the CI system can
    # delete them after results are archived within Jenkins
    ${DOCKER_RUN} bash -c "find \
        /workspace/${TEST_RESULTS_REL_DIR} -type d -exec chmod 775 {} +"

    ${DOCKER_RUN} bash -c "find \
        /workspace/${TEST_RESULTS_REL_DIR} -type f -exec chmod 664 {} +"
}

trap set_perms EXIT

# linting and pep8 style check (configured by .flake8 and .pylintrc)
${DOCKER_RUN} flake8 \
    --config ${CONTAINER_HOME}/opera/.flake8 \
    --jobs auto \
    --exit-zero \
    --application-import-names opera \
    --output-file /workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/flake8.log \
    ${CONTAINER_HOME}/opera

${DOCKER_RUN} pylint \
    --rcfile=${CONTAINER_HOME}/opera/.pylintrc \
    --jobs 0 \
    --exit-zero \
    --output=/workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/pylint.log \
    --enable-all-extensions \
    ${CONTAINER_HOME}/opera

# pytest (including code coverage)
${DOCKER_RUN} bash -c "pytest \
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
    /workspace/src/opera/test/util > /workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/pytest.log 2>&1"

echo "CSLC-S1 PGE Docker image test complete"

exit 0
