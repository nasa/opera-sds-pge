#!/bin/bash

# Script used to orchestrate the pairwise comparison of output and expected
# CAL-DISP products. Each individual pair of products is compared using the
# SAS validate workflow

set -e
umask 002

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/../util/test_int_util.sh

# Set up the expected directory paths within the container
# These are determined by the docker volume mounting that occurs in test_int_tropo.sh
OUTPUT_DIR="/home/conda/output_dir"
EXPECTED_DIR="/home/conda/expected_output_dir"
PGE_NAME="cal_disp"

# Validate that OUTPUT_DIR and EXPECTED_DIR exist within the container
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Error: Output directory '$OUTPUT_DIR' does not exist." >&2
    exit 1
fi

if [ ! -d "$EXPECTED_DIR" ]; then
    echo "Error: Expected directory '$EXPECTED_DIR' does not exist." >&2
    exit 1
fi

echo "TODO: Run comparison"
touch "${OUTPUT_DIR}/test_int_${PGE_NAME}_results.html"

exit 0
