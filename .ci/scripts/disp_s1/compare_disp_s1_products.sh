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

PGE_NAME="disp_s1"

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

echo "<tr><th>Compare Result</th><th><ul><li>Expected file</li><li>Output file</li></ul></th><th>disp_s1_compare.py output</th></tr>" >> "$RESULTS_FILE"

# overall_status values and their meaning
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

for output_file in "$OUTPUT_DIR"/*
do
    compare_out="N/A"
    compare_result="N/A"
    expected_file="N/A"
    compare_exit_status=0

    echo "Evaluating output file $output_file"

    if [[ "${output_file##*/}" == *.nc ]]
    then
        output_file=$(basename ${output_file})
        output_file_dates="${output_file%%.*}"

        echo "Output product date range is ${output_file_dates}"

        # Find the matching expected output product based on date range
        for potential_file in "$EXPECTED_DIR"/*.nc
        do
            if [[ "$potential_file" == *"${output_file_dates}.nc" ]]; then
                expected_file=$potential_file
                echo "Expected output file is $expected_file"
                break
            fi
        done

        if [ ! -f "$expected_file" ]; then
            echo "No expected file found for product $output_file in expected directory $EXPECTED_DIR"
            overall_status=1
        else
            compare_out=$(${SCRIPT_DIR}/disp_s1_compare.py \
                --golden "${expected_file}" --test "${OUTPUT_DIR}/${output_file}" \
                --exclude_groups pge_runconfig dolphin_workflow_config dolphin_workflow_config algorithm_parameters_yaml ) || compare_exit_status=$?

            if [[ $compare_exit_status -ne 0 ]]; then
                echo "File comparison failed. Output and expected files differ for ${output_file}"
                compare_result="FAIL"
                overall_status=2
            else
                echo "File comparison passed for ${output_file}"
                compare_result="PASS"
            fi
        fi
    else
        echo "Not comparing file ${output_file}"
        compare_result="SKIPPED"
    fi

    # add html breaks to newlines
    compare_out="${compare_out//$'\n'/<br>}"
    update_html_results_file "${compare_result}" "${output_file}" "${expected_file}" "${compare_out}"
done

finalize_html_results_file

# Write the status code to an RC file so the integration test script can pick
# it up.
echo $overall_status > $OUTPUT_DIR/"compare_disp_s1_products.rc"

# Always want to return 0 even if some comparisons failed to avoid error handling
# logic in the PGE
exit 0
