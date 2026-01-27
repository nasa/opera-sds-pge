#!/bin/bash
# Script to execute unit tests on the OPERA CAL-DISP PGE Docker image

set -e

# Source the build script utility functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

. "${SCRIPT_DIR}"/../util/util.sh

# Parse args
parse_build_args "$@"

echo '
=====================================

Testing CAL-DISP PGE Docker image...

=====================================
'

PGE_NAME="cal_disp"
IMAGE="opera_pge/${PGE_NAME}"
TEST_RESULTS_REL_DIR="test_results"
CONTAINER_HOME="/home/conda"
CONDA_ROOT="/opt/conda"

# defaults
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../../..)
[ -z "${TAG}" ] && TAG="${USER}-dev"

TEST_RESULTS_DIR="${WORKSPACE}/${TEST_RESULTS_REL_DIR}/${PGE_NAME}"

echo "Test results output directory: ${TEST_RESULTS_DIR}"
mkdir --parents ${TEST_RESULTS_DIR}
chmod -R 775 ${TEST_RESULTS_DIR}

# Use the environment of the docker image to run linting, tests, etc...
# Note the change of working directory (-w) to a directory without
# Python code so that import statements favor Python code found in the
# Docker image rather than code found on the host.
DOCKER_RUN="docker run --rm \
    -v ${WORKSPACE}:/workspace \
    -v ${WORKSPACE}/src/opera/test/__init__.py:${CONTAINER_HOME}/opera/test/__init__.py \
    -v ${WORKSPACE}/src/opera/test/pge/base:${CONTAINER_HOME}/opera/test/pge/base \
    -v ${WORKSPACE}/src/opera/test/pge/${PGE_NAME}:${CONTAINER_HOME}/opera/test/pge/${PGE_NAME} \
    -v ${WORKSPACE}/src/opera/test/scripts:${CONTAINER_HOME}/opera/test/scripts \
    -v ${WORKSPACE}/src/opera/test/util:${CONTAINER_HOME}/opera/test/util \
    -v ${WORKSPACE}/src/opera/test/data:${CONTAINER_HOME}/opera/test/data \
    -e PYLINTHOME=/workspace/${TEST_RESULTS_REL_DIR}/.cache/pylint \
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
${DOCKER_RUN} bash -c "micromamba run -n cal-disp flake8 \
    --config ${CONTAINER_HOME}/opera/.flake8 \
    --jobs auto \
    --exit-zero \
    --application-import-names opera \
    --output-file /workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/flake8.log \
    ${CONTAINER_HOME}/opera"

${DOCKER_RUN} bash -c "export HOME=/home/conda/opera; micromamba run -n cal-disp pylint \
    --rcfile=${CONTAINER_HOME}/opera/.pylintrc \
    --jobs 0 \
    --exit-zero \
    --output=/workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/pylint.log \
    --enable-all-extensions \
    ${CONTAINER_HOME}/opera"

# pytest (including code coverage)
${DOCKER_RUN} bash -c "micromamba run -n cal-disp pytest -p no:cacheprovider \
    --junit-xml=/workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/pytest-junit.xml \
    --cov=${CONTAINER_HOME}/opera/pge/base \
    --cov=${CONTAINER_HOME}/opera/pge/${PGE_NAME} \
    --cov=${CONTAINER_HOME}/opera/scripts \
    --cov=${CONTAINER_HOME}/opera/util \
    --cov-report=term \
    --cov-report=html:/workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/coverage_html \
    ${CONTAINER_HOME}/opera/test/pge/base \
    ${CONTAINER_HOME}/opera/test/pge/${PGE_NAME} \
    ${CONTAINER_HOME}/opera/test/scripts \
    ${CONTAINER_HOME}/opera/test/util > /workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/pytest.log 2>&1"

echo "CAL-DISP PGE Docker image test complete"

exit 0
