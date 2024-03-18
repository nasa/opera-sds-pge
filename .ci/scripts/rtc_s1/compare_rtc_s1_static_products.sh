#!/bin/bash
  
# Script used to orchestrate the pairwise comparison of output and expected
# RTC-S1 products. 

set -e
umask 002

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/../util/test_int_util.sh

# TODO: add validation that OUTPUT/EXPECTED exist within container
OUTPUT_DIR="/home/conda/output_dir"
EXPECTED_DIR="/home/conda/expected_output_dir"
PGE_NAME="rtc_s1"

initialize_html_results_file "$OUTPUT_DIR" "$PGE_NAME"

# overall_status values and their meaning
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

declare -a burst_ids=("t069_147169_iw3"
                      "t069_147170_iw3"
                      "t069_147171_iw3"
                      "t069_147172_iw3"
                      "t069_147173_iw3"
                      "t069_147174_iw3"
                      "t069_147175_iw3"
                      "t069_147176_iw3"
                      "t069_147177_iw3"
                      "t069_147178_iw3")

update_html_results_file "${rtc_compare_result}" "${expected_files}" "${output_files}" "${compare_output}"

static_layers_compare_result="PENDING"
expected_dir="${TMP_DIR}/${EXPECTED_DATA%.*}/expected_rtc_s1_static_output_dir"

static_burst_id_pattern="OPERA_L2_RTC-S1-STATIC_${burst_id_replace_underscores}_*.tif"
output_static_files="${static_output_dir}/${burst_id}"
expected_static_files="${expected_dir}/${burst_id}"

# Move the products for the current burst ID into their own subdir to compare
# against the expected
mkdir -p "${output_static_files}"
mv ${static_output_dir}/${static_burst_id_pattern} ${output_static_files}

echo "Output static layers matching burst id are in $output_static_files"
echo "Expected files are in $expected_static_files"

compare_output=$("${SCRIPT_DIR}"/../rtc_s1/rtc_s1_compare.py "${expected_static_files}" "${output_static_files}")

echo "$compare_output"
if [[ "$compare_output" != *"FAILED"* ]]; then
    echo "Product validation was successful for $output_static_files"
    static_layers_compare_result="PASS"
else
    echo "Failure: Some comparisons failed for $output_static_files"
    static_layers_compare_result="FAIL"
    overall_status=2
fi

# remove ansi colors from string
compare_output="$(echo "$compare_output" | sed -e 's/\x1b\[[0-9;]*m//g')"

# add html breaks to newlines
compare_output=${compare_output//$'\n'/<br>$'\n'}

finalize_html_results_file

# Write the status code to an RC file so the integration test script can pick
# it up.
echo $overall_status > $OUTPUT_DIR/"compare_rtc_s1_products.rc"

# Always want to return 0 even if some comparisons failed to avoid error handling
# logic in the PGE
exit 0


