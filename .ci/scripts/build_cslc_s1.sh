#!/bin/bash
set -e

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      echo "Usage: build_cslc_s1.sh [-h|--help] [-s|--sas-image <image name>] [-t|--tag <tag>] [-w|--workspace <path>]"
      exit 0
      ;;
    -s|--sas-image)
      SAS_IMAGE=$2
      shift
      shift
      ;;
    -t|--tag)
      TAG=$2
      shift
      shift
      ;;
    -w|--workspace)
      WORKSPACE=$2
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

echo '
=====================================

Building CSLC-S1 PGE docker image...

=====================================
'

PGE_NAME="cslc_s1"
IMAGE="opera_pge/${PGE_NAME}"
BUILD_DATE_TIME=$(date -u +'%Y-%m-%dT%H:%M:%SZ')

# defaults, SAS image should be updated as necessary for new image releases from ADT
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../..)
[ -z "${TAG}" ] && TAG="${USER}-dev"
[ -z "${SAS_IMAGE}" ] && SAS_IMAGE="artifactory-fn.jpl.nasa.gov:16001/gov/nasa/jpl/opera/adt/opera/cslc_s1:interface_0.1"

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
function cleanup {
  if [[ -z ${KEEP_TEMP_FILES} ]]; then
    echo "Cleaning up staging directory ${STAGING_DIR}..."
    rm -rf ${STAGING_DIR}
  fi
}

trap cleanup EXIT

# Copy files to the staging area and build the PGE docker image
mkdir -p ${STAGING_DIR}/opera/pge

cp ${WORKSPACE}/src/opera/__init__.py \
   ${STAGING_DIR}/opera/

cp ${WORKSPACE}/src/opera/_package.py \
   ${STAGING_DIR}/opera/

cp ${WORKSPACE}/src/opera/pge/__init__.py \
   ${STAGING_DIR}/opera/pge/

cp -r ${WORKSPACE}/src/opera/pge/base \
      ${STAGING_DIR}/opera/pge/

cp -r ${WORKSPACE}/src/opera/pge/${PGE_NAME} \
      ${STAGING_DIR}/opera/pge/

cp -r ${WORKSPACE}/src/opera/scripts \
      ${STAGING_DIR}/opera/

cp -r ${WORKSPACE}/src/opera/util \
      ${STAGING_DIR}/opera/

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
    --build-arg SAS_IMAGE=${SAS_IMAGE} \
    --build-arg BUILD_DATE_TIME=${BUILD_DATE_TIME} \
    --build-arg BUILD_VERSION=${TAG} \
    --build-arg PGE_SOURCE_DIR=$(basename ${STAGING_DIR}) \
    --file ${WORKSPACE}/.ci/docker/Dockerfile_${PGE_NAME} ${WORKSPACE}

echo "CSLC-S1 PGE Docker image build complete"

exit 0
