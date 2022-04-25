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
# Script to test all OPERA PGE Docker images
#

echo '
=======================================

Testing all OPERA PGE docker images...

=======================================
'

TAG=$1

# defaults
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../..)
[ -z "${TAG}" ] && TAG="${USER}-dev"

echo "WORKSPACE: $WORKSPACE"
echo "TAG: $TAG"

# check .ci scripts directory exists
if [ ! -d "${WORKSPACE}/.ci" ]; then
  echo "Error: the .ci directory doesn't exist at ${WORKSPACE}/.ci"
  exit 1
fi

# Build all of the Docker images
BUILD_SCRIPTS_DIR=${WORKSPACE}/.ci/scripts
${BUILD_SCRIPTS_DIR}/test_dswx_hls.sh --tag ${TAG} --workspace ${WORKSPACE}

echo 'Build Complete'

exit 0
