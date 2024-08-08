#!/bin/bash

set +xe

echo '
===============================================

Scanning workspace for potential leaked secrets

===============================================
'


# defaults
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../../..)

echo "WORKSPACE: $WORKSPACE"

if [ ! -f ${WORKSPACE}/.secrets.baseline ] ;
then
    # This generated baseline file will only be temporarily available on the GitHub side and will not appear in the user's local files.
    # Scanning an empty folder to generate an initial .secrets.baseline without secrets in the results.
    echo "⚠️ No existing .secrets.baseline file detected. Creating a new blank baseline file."
    mkdir -p ${WORKSPACE}/empty-dir
    detect-secrets -C ${WORKSPACE}/empty-dir scan > ${WORKSPACE}/.secrets.baseline
    echo "✅ Blank .secrets.baseline file created successfully."
    rm -r ${WORKSPACE}/empty-dir
else
    echo "✅ Existing .secrets.baseline file detected. No new baseline file will be created."
fi
# scripts scan repository for new secrets
# backup list of known secrets
cp -pr ${WORKSPACE}/.secrets.baseline ${WORKSPACE}/.secrets.new
# find secrets in the repository
detect-secrets -C ${WORKSPACE} scan \
                    --disable-plugin AbsolutePathDetectorExperimental \
                    --all-files \
                    --baseline ${WORKSPACE}/.secrets.new \
                    --exclude-files '\.secrets..*' \
                    --exclude-files '\.git.*' \
                    --exclude-files 'test_results' \
                    --exclude-files '\.pytest_cache' \
                    --exclude-files '\.venv' \
                    --exclude-files 'venv' \
                    --exclude-files 'dist' \
                    --exclude-files 'build' \
                    --exclude-files '.*\.egg-info'
# break build when new secrets discovered
# function compares baseline/new secrets w/o listing results -- success(0) when new secret found

jq -r '.results | keys[] as $key | "\($key),\(.[$key] | .[] | .hashed_secret)"' "${WORKSPACE}/.secrets.baseline" | sort > /data/tmp/.secrets.1
jq -r '.results | keys[] as $key | "\($key),\(.[$key] | .[] | .hashed_secret)"' "${WORKSPACE}/.secrets.new" | sort > /data/tmp/.secrets.2

diff /data/tmp/.secrets.1 /data/tmp/.secrets.2 > ${WORKSPACE}/.secrets.diff || true

rm -f /data/tmp/.secrets.1 /data/tmp/.secrets.2
