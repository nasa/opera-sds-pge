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
# Script to build the OPERA DSWx-HLS PGE Docker image
#

echo '
=====================================

Building DSWx-HLS PGE docker image...

=====================================
'

set -e

IMAGE='opera_pge/dswx_hls'
TAG=$1
WORKSPACE=$2
BUILD_DATE_TIME=$(date -u +'%Y-%m-%dT%H:%M:%SZ')

# defaults
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../..)
[ -z "${TAG}" ] && TAG="${USER}-dev"

echo "WORKSPACE: $WORKSPACE"
echo "IMAGE: $IMAGE"
echo "TAG: $TAG"

# Check that the .ci scripts directory exists
if [ ! -d "${WORKSPACE}/.ci" ]; then
  echo "Error: the .ci directory doesn't exist at ${WORKSPACE}/.ci"
  exit 1
fi

# Create a directory on the host to use as a staging area for files to be
# copied into the resulting Docker image.
STAGING_DIR=$(mktemp -d -p ${WORKSPACE} docker_image_staging_XXXXXXXXXX)

# Configure a trap to clean up on exit regardless of whether the build succeeds
function cleanup {
  if [[ -z ${KEEP_TEMP_FILES} ]]; then
    echo "Cleaning up staging directory ${STAGING_DIR}..."
    rm -rf ${STAGING_DIR}
  fi
}

trap cleanup EXIT

# Copy files to the staging area and build the PGE docker image
cp -r ${WORKSPACE}/src/opera \
      ${STAGING_DIR}/

cp ${WORKSPACE}/COPYING \
   ${STAGING_DIR}/opera

cp ${WORKSPACE}/requirements.txt \
   ${STAGING_DIR}/opera

cp ${WORKSPACE}/.flake8 \
   ${STAGING_DIR}/opera

cp ${WORKSPACE}/.pylintrc \
   ${STAGING_DIR}/opera

# Create a VERSION file in the staging area to track version and build time
printf "pge_version: ${TAG}\npge_build_datetime: ${BUILD_DATE_TIME}\n" \
    > ${STAGING_DIR}/opera/VERSION \

# Remove the old Docker image, if it exists
EXISTING_IMAGE_ID=$(docker images -q ${IMAGE}:${TAG})
if [[ ! -z ${EXISTING_IMAGE_ID} ]]; then
  docker rmi ${EXISTING_IMAGE_ID}
fi

# Build the PGE docker image
docker build --rm --force-rm -t ${IMAGE}:${TAG} \
    --build-arg BUILD_DATE_TIME=${BUILD_DATE_TIME} \
    --build-arg BUILD_VERSION=${TAG} \
    --build-arg PGE_SOURCE_DIR=$(basename ${STAGING_DIR}) \
    --file ${WORKSPACE}/.ci/docker/Dockerfile_dswx_hls ${WORKSPACE}

exit $?
