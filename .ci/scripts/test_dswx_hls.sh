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

echo '
=====================================

Testing DSWx-HLS PGE Docker image...

=====================================
'

IMAGE="opera_pge/dswx_hls"
TAG=$1
WORKSPACE=$2
TEST_RESULTS_REL_DIR="test_results/dswx_hls"

# defaults
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../..)
[ -z "${TAG}" ] && TAG="${USER}-dev"

echo "Test results output directory:  ${WORKSPACE}/${TEST_RESULTS_REL_DIR}"
mkdir --mode=775 --parents ${WORKSPACE}/${TEST_RESULTS_REL_DIR}

# Use the environment of the docker image to run linting, tests, etc...
DOCKER_RUN="docker run --rm \
    -v ${WORKSPACE}:/workspace \
    -u conda:conda \
    --entrypoint /opt/conda/bin/pge_tests_entrypoint.sh \
    ${IMAGE}:${TAG}"

# linting and pep8 style check (configured by .flake8 and .pylintrc)
${DOCKER_RUN} flake8 \
    --config /home/conda/opera/.flake8 \
    --jobs auto \
    --application-import-names opera \
    --output-file /workspace/${TEST_RESULTS_REL_DIR}/flake8.log \
    /home/conda/opera

${DOCKER_RUN} pylint \
    --rcfile=/home/conda/opera/.pylintrc \
    --jobs 0 \
    --output=/workspace/${TEST_RESULTS_REL_DIR}/pylint.log \
    --enable-all-extensions \
    /home/conda/opera

# pytest (including code coverage)
${DOCKER_RUN} bash -c "pytest \
    --junit-xml=/workspace/${TEST_RESULTS_REL_DIR}/pytest-junit.xml \
    --cov=/home/conda/opera/pge \
    --cov=/home/conda/opera/scripts \
    --cov=/home/conda/opera/util \
    --cov-report=term \
    --cov-report=html:/workspace/${TEST_RESULTS_REL_DIR}/coverage_html \
    /home/conda/opera > /workspace/${TEST_RESULTS_REL_DIR}/pytest.log 2>&1"

# Open up permissions on all output reports so the CI system can delete them
# after they're archived within Jenkins
${DOCKER_RUN} bash -c "chmod \
    -R 775 /workspace/${TEST_RESULTS_REL_DIR}/"

echo "DSWx-HLS PGE Docker image test complete"

exit 0
