#!/bin/bash

# Script used to orchestrate the pairwise comparison of output and expected
# DSWx-S1 products. Each individual pair of products is compared using the
# dswx_s1_compare.py script.

set -e
umask 002

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/../util/test_int_util.sh

OUTPUT_DIR="/home/dswx_user/output_dir"

EXPECTED_DIR="/home/dswx_user/expected_output_dir"

PGE_NAME="dswx_s1"

# Validate that OUTPUT_DIR and EXPECTED_DIR exist within the container
if [ ! -d "$OUTPUT_DIR" ]; then
    echo "Error: Output directory '$OUTPUT_DIR' does not exist." >&2
    exit 1
fi

if [ ! -d "$EXPECTED_DIR" ]; then
    echo "Error: Expected directory '$EXPECTED_DIR' does not exist." >&2
    exit 1
fi

initialize_html_results_file "$output_dir" "$PGE_NAME"

# Compare output files against expected files
for output_file in "$output_dir"/*
do
    compare_output="N/A"
    compare_result="N/A"
    expected_file="N/A"

    echo "output_file $output_file"
    output_file=$(basename -- "$output_file")

    if [[ "${output_file##*/}" == *.tif* ]]
    then
        for potential_product in B01_WTR B02_BWTR B03_CONF B04_DIAG
        do
            if [[ "$output_file" == *"$potential_product"* ]]; then
                product=$potential_product
                break
            fi
        done

        echo "product is $product"

        # Parse the tile code from the filename
        IFS='_' read -ra ARR <<< "$output_file"
        tile_code=${ARR[3]}

        echo "tile code is $tile_code"

        for potential_file in "$expected_data_dir"/*.tif*
        do
            if [[ "$potential_file" == *"$tile_code"*"$product"* ]]; then
                echo "expected file is $potential_file"
                expected_file=$potential_file
                break
            fi
        done

        if [ ! -f "$expected_file" ]; then
            echo "No expected file found for product $product in expected directory $expected_data_dir"
            overall_status=1
            compare_result="FAIL"
            compare_output="FAILED"
        else
           # compare output and expected files
           echo "python3 dswx_comparison.py $(basename -- ${expected_file}) ${output_file}"
           compare_output=$(python3 $SCRIPT_DIR/dswx_comparison.py ${expected_file} ${output_dir}/${output_file})
           echo "$compare_output"
        fi

        if [[ "$compare_output" != *"FAIL"* ]]; then
            echo "Product validation was successful for $output_file"
            compare_result="PASS"
        else
            echo "Failure: Some comparisons failed for $output_file"
            compare_result="FAIL"
            overall_status=2
        fi
    else
        echo "Not comparing file ${output_file}"
        compare_result="SKIPPED"
    fi

    # add html breaks to newlines
    compare_output=${compare_output//$'\n'/<br>$'\n'}

    update_html_results_file "${compare_result}" "${output_file}" "${expected_file}" "${compare_output}"
done

finalize_html_results_file
cp "${output_dir}"/test_int_dswx_s1_results.html "${TEST_RESULTS_DIR}"/test_int_dswx_s1_results.html

# Write the status code to an RC file so the integration test script can pick it up.
echo $overall_status > $OUTPUT_DIR/"compare_dswx_s1_products.rc"

# Always want to return 0 even if some comparisons failed to avoid error handling logic in the PGE
exit 0