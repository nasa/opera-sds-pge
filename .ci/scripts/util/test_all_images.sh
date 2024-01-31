#!/bin/bash
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
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../../..)
[ -z "${TAG}" ] && TAG="${USER}-dev"

echo "WORKSPACE: $WORKSPACE"
echo "TAG: $TAG"

# check .ci scripts directory exists
if [ ! -d "${WORKSPACE}/.ci" ]; then
  echo "Error: the .ci directory doesn't exist at ${WORKSPACE}/.ci"
  exit 1
fi

# Build all of the Docker images
# options:
# --tag: docker file tag (defaults to <user_name>-dev)
# --workspace: path to the .ci directory in the user repository
# --no-cleanup: (optional) disable the automatic deletion of the temporary working directory after the script completes.
# --no-metrics: (optional) disable the metrics collection that occurs during PGE execution.
BUILD_SCRIPTS_DIR=${WORKSPACE}/.ci/scripts
${BUILD_SCRIPTS_DIR}/dswx_hls/test_dswx_hls.sh --tag ${TAG} --workspace ${WORKSPACE} --no-cleanup --no-metrics
${BUILD_SCRIPTS_DIR}/cslc_s1/test_cslc_s1.sh --tag ${TAG} --workspace ${WORKSPACE}
${BUILD_SCRIPTS_DIR}/rtc_s1/test_rtc_s1.sh --tag ${TAG} --workspace ${WORKSPACE} --no-cleanup --no-metrics
${BUILD_SCRIPTS_DIR}/dswx_s1/test_dswx_s1.sh --tag ${TAG} --workspace ${WORKSPACE}
${BUILD_SCRIPTS_DIR}/disp_s1/test_disp_s1.sh --tag ${TAG} --workspace ${WORKSPACE} --no-cleanup --no-metrics

echo 'Build Complete'

exit 0
