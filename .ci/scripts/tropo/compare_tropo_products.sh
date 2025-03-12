#!/bin/bash

# Script used to orchestrate the pairwise comparison of output and expected
# TROPO products. Each individual pair of products is compared using the
# tropo_comparison.py script

set -e
umask 002

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/../util/test_int_util.sh

# Set up the expected directory paths within the container
# These are determined by the docker volume mounting that occurs in test_int_tropo.sh
# TODO: set actual values
OUTPUT_DIR="/home/ops/output_dir"
EXPECTED_DIR="/home/ops/expected_output_dir"
PGE_NAME="tropo"

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

    # Comparison script only compares netcdf outputs
    if [[ "${output_file##*/}" == *.nc ]]
    then

        # Need to match output_file with expected output_filename
        # OPERA_L4_TROPO_20190613T060000Z_20250208T180402Z_HRES_0.1_v0.1.nc -> golden_output_20190613T06.nc\
        output_file=$(basename ${output_file})
        # Extract %Y%m%dT%H portion of filename
        output_file_date=$(echo "$output_file" | cut -d'_' -f4 | cut -c1-11)

        echo "Output product is ${output_file} with file date ${output_file_date}"

        # Find the matching expected output product based on date range
        for potential_file in "$EXPECTED_DIR"/*.nc
        do
            if [[ "$potential_file" == *"${output_file_date}.nc" ]]; then
                expected_file=$potential_file
                echo "Expected output file is $expected_file"
                break
            fi
        done

        if [ ! -f "$expected_file" ]; then
            echo "No expected file found for product $output_file in expected directory $EXPECTED_DIR"
            overall_status=1
        else
            echo "Running validation script on golden_output/$(basename $expected_file) and output/${output_file}"
            opera_tropo validate $expected_file ${OUTPUT_DIR}/${output_file}
            
            compare_exit_status=$?

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
echo $overall_status > $OUTPUT_DIR/"compare_tropo_products.rc"

# Always want to return 0 even if some comparisons failed to avoid error handling
# logic in the PGE
exit 0