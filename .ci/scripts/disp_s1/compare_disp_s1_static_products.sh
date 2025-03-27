#!/bin/bash

# Script used to orchestrate the pairwise comparison of output and expected
# DISP-S1 products. Each individual pair of products is compared using the
# disp_s1_compare.py script

set -e
umask 002

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/../util/test_int_util.sh

# Set up the expected directory paths within the container
# These are determined by the docker volume mounting that occurs in test_int_disp_s1.sh
OUTPUT_DIR="/home/mamba/output_dir"
EXPECTED_DIR="/home/mamba/expected_output_dir"

PGE_NAME="disp_s1_static"

# Validate that OUTPUT_DIR and EXPECTED_DIR exist within the container
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Error: Output directory '$OUTPUT_DIR' does not exist." >&2
    exit 1
fi

if [ ! -d "$EXPECTED_DIR" ]; then
    echo "Error: Expected directory '$EXPECTED_DIR' does not exist." >&2
    exit 1
fi

initialize_html_results_file "$OUTPUT_DIR" "$PGE_NAME"

echo "<tr><th>Compare Result</th><th><ul><li>Expected file</li><li>Output file</li></ul></th><th>Comparison output</th></tr>" >> "$RESULTS_FILE"

# overall_status values and their meaning
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

compare_out="N/A"
compare_result="N/A"
expected_file="${EXPECTED_DIR}"
output_file="${OUTPUT_DIR}"
compare_exit_status=0

echo "Evaluating output directory $output_file"

compare_out=$(disp-s1 validate-static-layers $expected_file $output_file 2>&1)
compare_exit_status=$?

if [[ $compare_exit_status -ne 0 ]]; then
    echo "Output comparison failed. Output and expected files differ for ${output_file}"
    compare_result="FAIL"
    overall_status=2
else
    echo "Output comparison passed for ${output_file}"
    compare_result="PASS"
fi

# add html breaks to newlines
compare_out="${compare_out//$'\n'/<br>}"
update_html_results_file "${compare_result}" "${output_file}" "${expected_file}" "${compare_out}"

finalize_html_results_file

# Write the status code to an RC file so the integration test script can pick
# it up.
echo $overall_status > $OUTPUT_DIR/"compare_disp_s1_static_products.rc"

# Always want to return 0 even if some comparisons failed to avoid error handling
# logic in the PGE
exit 0
