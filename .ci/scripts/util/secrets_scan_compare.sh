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
    echo "1️⃣ Run the 'detect-secrets' tool on your local machine. This tool will identify and clean up the secrets. You can find detailed instructions at this link: https://nasa-ammos.github.io/slim/continuous-testing/starter-kits/#detect-secrets" >&2
    echo "" >&2
    echo "2️⃣ After cleaning up the secrets, commit your changes and re-push your update to the repository." >&2
    echo "" >&2
    echo "Your efforts to maintain the security of our codebase are greatly appreciated!" >&2
    exit 1
else
    echo "🟢 Secrets tests PASSED! 🟢" >&1
    echo "No new secrets were detected in comparison to any baseline configurations."  >&1
    exit 0
fi