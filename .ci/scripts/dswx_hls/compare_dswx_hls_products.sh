#!/bin/bash

# Script used to orchestrate the pairwise comparison of output and expected
# DSWx-HLS products. Each individual pair of products is compared using the
# dswx_hls_compare.py script.

set -e
umask 002

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/../util/test_int_util.sh

# TODO: add validation that OUTPUT/EXPECTED exist within container
OUTPUT_DIR="/home/conda/output_dir"
EXPECTED_DIR="/home/conda/expected_output_dir"
PGE_NAME="dswx_hls"

initialize_html_results_file "$OUTPUT_DIR" "$PGE_NAME"

# overall_status values and their meaning
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

# Compare output files against expected files
for output_file in "$OUTPUT_DIR"/*
do
    compare_out="N/A"
    compare_result="N/A"
    expected_file="N/A"

    echo "Evaluating output file $output_file"

    if [[ "${output_file##*/}" == *.tif* ]]
    then
        # Determine the type of the current output product
        for potential_product in B01_WTR B02_BWTR B03_CONF B04_DIAG B05_WTR-1 B06_WTR-2 B07_LAND B08_SHAD B09_CLOUD B10_DEM BROWSE
        do
            if [[ "$output_file" == *"$potential_product"* ]]; then
                product=$potential_product
                break
            fi
        done

        echo "Product type is $product"

        # Find the matching product type in the list of expected products
        for potential_file in "$EXPECTED_DIR"/*.tif*
        do
            if [[ "$potential_file" == *"$product"* ]]; then
                expected_file=$potential_file
                echo "Expected output file is $expected_file"
                break
            fi
        done

        if [ ! -f "$expected_file" ]; then
            echo "No expected file found for product type $product in expected directory $EXPECTED_DIR"
            overall_status=1
        else
            # Compare the output and expected files with the Python script
            # furnished from ADT
            compare_out=$("$SCRIPT_DIR"/dswx_hls_compare.py \
                          "${output_file}" "${expected_file}" -x "PRODUCT_VERSION")

            echo "$compare_out"

            if [[ "$compare_out" == *"[FAIL]"* ]]; then
                echo "File comparison failed. Output and expected files differ for ${output_file}"
                compare_result="FAIL"
                overall_status=2
            elif [[ "$compare_out" == *"ERROR"* ]]; then
                echo "An error occurred during file comparison."
                compare_result="ERROR"
                overall_status=1
            else
                echo "File comparison passed for ${output_file}"
                compare_result="PASS"
            fi
        fi
    else
        echo "Not comparing file ${output_file}"
        compare_result="SKIPPED"
    fi

    compare_out="${compare_out//$'\n'/<br>}"
    update_html_results_file "${compare_result}" "${output_file}" "${expected_file}" "${compare_out}"
done

finalize_html_results_file

# Write the status code to an RC file so the integration test script can pick
# it up.
echo $overall_status > $OUTPUT_DIR/"compare_dswx_hls_products.rc"

# Always want to return 0 even if some comparisons failed to avoid error handling
# logic in the PGE
exit 0