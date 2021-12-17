#!/bin/bash
#
# Copyright 2021, by the California Institute of Technology.
# ALL RIGHTS RESERVED.
# United States Government sponsorship acknowledged.
# Any commercial use must be negotiated with the Office of Technology Transfer
# at the California Institute of Technology.
# This software may be subject to U.S. export control laws and regulations.
# By accepting this document, the user agrees to comply with all applicable
# U.S. export laws and regulations. User has the responsibility to obtain
# export licenses, or other export authority as may be required, before
# exporting such information to foreign countries or providing access to
# foreign persons.
#
# Script to execute tests on OPERA DSWx-HLS PGE Docker image
#

set -e

echo '
=====================================

Testing DSWx-HLS PGE Docker image...

=====================================
'

PGE_NAME="dswx_hls"
IMAGE="opera_pge/${PGE_NAME}"
TEST_RESULTS_REL_DIR="test_results"

TAG=$1
WORKSPACE=$2

# defaults
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../..)
[ -z "${TAG}" ] && TAG="${USER}-dev"

TEST_RESULTS_DIR="${WORKSPACE}/${TEST_RESULTS_REL_DIR}/${PGE_NAME}"

echo "Test results output directory: ${TEST_RESULTS_DIR}"
mkdir --mode=775 --parents ${TEST_RESULTS_DIR}
chmod -R 775 ${TEST_RESULTS_DIR}

# Use the environment of the docker image to run linting, tests, etc...
# Note the change of working directory (-w) to a directory without
# Python code so that import statements favor Python code found in the
# Docker image rather than code found on the host.
DOCKER_RUN="docker run --rm \
    -v ${WORKSPACE}:/workspace \
    -w /workspace/${TEST_RESULTS_REL_DIR}
    -u ${UID}:$(id -g) \
    --entrypoint /opt/conda/bin/pge_tests_entrypoint.sh \
    ${IMAGE}:${TAG}"

# Configure a trap to set permissions on exit regardless of whether the testing succeeds
function set_perms {
    # Open up permissions on all test results we can be sure the CI system can
    # delete them after they're archived within Jenkins
    ${DOCKER_RUN} bash -c "find \
        /workspace/${TEST_RESULTS_REL_DIR} -type d -exec chmod 775 {} +"

    ${DOCKER_RUN} bash -c "find \
        /workspace/${TEST_RESULTS_REL_DIR} -type f -exec chmod 664 {} +"
}

trap set_perms EXIT

# linting and pep8 style check (configured by .flake8 and .pylintrc)
${DOCKER_RUN} flake8 \
    --config /home/conda/opera/.flake8 \
    --jobs auto \
    --exit-zero \
    --application-import-names opera \
    --output-file /workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/flake8.log \
    /home/conda/opera

${DOCKER_RUN} pylint \
    --rcfile=/home/conda/opera/.pylintrc \
    --jobs 0 \
    --exit-zero \
    --output=/workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/pylint.log \
    --enable-all-extensions \
    /home/conda/opera

# pytest (including code coverage)
${DOCKER_RUN} bash -c "pytest \
    --junit-xml=/workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/pytest-junit.xml \
    --cov=/home/conda/opera/pge \
    --cov=/home/conda/opera/scripts \
    --cov=/home/conda/opera/util \
    --cov-report=term \
    --cov-report=html:/workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/coverage_html \
    /workspace/src/opera/test > /workspace/${TEST_RESULTS_REL_DIR}/${PGE_NAME}/pytest.log 2>&1"

echo "DSWx-HLS PGE Docker image test complete"

exit 0
