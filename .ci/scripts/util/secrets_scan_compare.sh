#!/bin/bash

set +xe

echo '
============================================

Comparing secrets scan results with baseline

============================================
'


# defaults
[ -z "${WORKSPACE}" ] && WORKSPACE=$(realpath $(dirname $(realpath $0))/../../..)

echo "WORKSPACE: $WORKSPACE"

if grep -q '>' < ${WORKSPACE}/.secrets.diff;
then
    echo "⚠️ Attention Required! ⚠️" >&2
    echo "New secrets have been detected in your recent commit. Due to security concerns, we cannot display detailed information here and we cannot proceed until this issue is resolved." >&2
    echo "" >&2
    echo "Please follow the steps below on your local machine to reveal and handle the secrets:" >&2
    echo "" >&2
    echo "1️⃣ Run the 'detect-secrets' tool on your local machine. This tool will identify and clean up the secrets:" >&2
    echo "" >&2
    echo "    \$ detect-secrets scan --all-files --disable-plugin AbsolutePathDetectorExperimental --exclude-files '\.secrets\..*' --exclude-files '\.git.*' --exclude-files 'test_results' --exclude-files '\.pytest_cache' --exclude-files '\.venv' --exclude-files 'venv' --exclude-files 'dist' --exclude-files 'build' --exclude-files '.*\.egg-info' > .secrets.baseline" >&2
    echo "" >&2
    echo "2️⃣ Perform an audit on the updated .secrets.baseline to disposition any new findings:" >&2
    echo "" >&2
    echo "    \$ detect-secrets audit .secrets.baseline" >&2
    echo "" >&2
    echo "❗NOTE: The audit tool will ask the following for all newly detected \"secrets\": \"Is this a secret that should be committed to this repository?\"" >&2
    echo "" >&2
    echo "❗If the detected secret is benign (i.e. a public email address or dummy password) the correct answer is \"y\"." >&2
    echo "" >&2
    echo "3️⃣ After auditing all new findings, commit the updated .secrets.baseline and push the update to origin." >&2
    echo "" >&2
    echo "Your efforts to maintain the security of our codebase are greatly appreciated!" >&2
    exit 1
else
    echo "🟢 Secrets tests PASSED! 🟢" >&1
    echo "No new secrets were detected in comparison to any baseline configurations."  >&1
    exit 0
fi