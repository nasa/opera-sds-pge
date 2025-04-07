#!/bin/bash
set -e

# Source the build script utility functions
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

. "${SCRIPT_DIR}"/../util/util.sh

# Parse args
parse_build_args "$@"

echo '
=====================================

Building DISP-NI PGE docker image...

=====================================
'

PGE_NAME="disp_ni"
IMAGE="opera_pge/${PGE_NAME}"
BUILD_DATE_TIME=$(date -u +'%Y-%m-%dT%H:%M:%SZ')

# defaults, SAS image should be updated as necessary for new image releases from ADT
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../../..)
[ -z "${TAG}" ] && TAG="${USER}-dev"
[ -z "${SAS_IMAGE}" ] && SAS_IMAGE="artifactory-fn.jpl.nasa.gov:16001/gov/nasa/jpl/opera/adt/opera/disp-nisar/0.1.1"

echo "WORKSPACE: $WORKSPACE"
echo "IMAGE: $IMAGE"
echo "TAG: $TAG"
echo "SAS_IMAGE: $SAS_IMAGE"

# Check that the .ci scripts directory exists
if [ ! -d "${WORKSPACE}/.ci" ]; then
  echo "Error: the .ci directory doesn't exist at ${WORKSPACE}/.ci"
  exit 1
fi

# Create a directory on the host to use as a staging area for files to be
# copied into the resulting Docker image.
STAGING_DIR=$(mktemp -d -p ${WORKSPACE} docker_image_staging_XXXXXXXXXX)

# Configure a trap to clean up on exit regardless of whether the build succeeds
trap build_script_cleanup EXIT

# Copy files to the staging area and build the PGE docker image
copy_pge_files $WORKSPACE $STAGING_DIR $PGE_NAME

# Create a VERSION file in the staging area to track version and build time
printf "pge_version: ${TAG}\npge_build_datetime: ${BUILD_DATE_TIME}\n" \
    > ${STAGING_DIR}/opera/VERSION \

# Remove the old Docker image, if it exists
EXISTING_IMAGE_ID=$(docker images -q ${IMAGE}:${TAG})
if [[ -n ${EXISTING_IMAGE_ID} ]]; then
  docker rmi ${EXISTING_IMAGE_ID}
fi

# Select the appropriate platform to target the container for.
# This is to support Apple M1 builds, which will default to (very slow) emulation
# if the incorrect platform is specified.
# Note that currently, the container build process on Apple M1 is significantly
# slower than for other architectures.
if [[ `uname -m` == "arm64" ]]; then
  PLATFORM='--platform linux/arm64'
else
  PLATFORM='--platform linux/amd64'
fi

# Build the PGE docker image
docker build ${PLATFORM} --progress plain --rm --force-rm -t ${IMAGE}:${TAG} \
    --build-arg SAS_IMAGE=${SAS_IMAGE} \
    --build-arg BUILD_DATE_TIME=${BUILD_DATE_TIME} \
    --build-arg BUILD_VERSION=${TAG} \
    --build-arg PGE_SOURCE_DIR=$(basename ${STAGING_DIR}) \
    --file ${WORKSPACE}/.ci/docker/Dockerfile_${PGE_NAME} ${WORKSPACE}

echo "DISP-NI PGE Docker image build complete"

exit 0
