#!/bin/bash

# Script used to orchestrate the pairwise comparison of output and expected
# CAL-DISP products. Each individual pair of products is compared using the
# SAS validate workflow

set -e
umask 002

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/../util/test_int_util.sh

# Set up the expected directory paths within the container
# These are determined by the docker volume mounting that occurs in test_int_cal_disp.sh
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

initialize_html_results_file "$OUTPUT_DIR" "$PGE_NAME"

echo "<tr><th>Compare Result</th><th><ul><li>Output file</li><li>Expected file</li></ul></th><th>opera_tropo validate output</th></tr>" >> "$RESULTS_FILE"

# overall_status values and their meaning
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

for output_product in "$OUTPUT_DIR"/*
do
  compare_output="N/A"
  compare_result="N/A"
  expected_product="N/A"
  compare_exit_status=0

  echo "output_product $output_product"
  output_product=$(basename -- "$output_product")

  # Parse the unique product ID from the filename
  IFS='_' read -ra ARR <<< "$output_product"
  product_id=$(echo "${ARR[@]:0:9}" | sed s'/ /_/g')

  # Comparison script only compares netcdf outputs
  if [[ "${output_product##*/}" == *.nc ]]
  then
    for potential_product in "$EXPECTED_DIR"/*.nc
    do
    potential_product=$(basename -- "$potential_product")

      if [[ "$potential_product" == "$product_id"* ]]; then
        echo "expected product is $potential_product"
        expected_product=$potential_product
        break
      fi
    done

    if [ ! -f ${EXPECTED_DIR}/"$expected_product" ]; then
      echo "No matching product found in expected directory $EXPECTED_DIR"
      overall_status=1
      compare_result="FAIL"
      compare_output="FAILED"
    else
       # compare output and expected files
       echo "cal-disp validate ${EXPECTED_DIR}/${expected_product} ${OUTPUT_DIR}/${output_product}"
       compare_output=$(cal-disp validate "${EXPECTED_DIR}/${expected_product}" "${OUTPUT_DIR}/${output_product}" 2>&1) || compare_exit_status=$?
       echo "$compare_output"

       if [[ $compare_exit_status -ne 0 ]]; then
            echo "File comparison failed. Output and expected files differ for ${output_product}"
            compare_result="FAIL"
            overall_status=2
       else
            echo "File comparison passed for ${output_product}"
            compare_result="PASS"
       fi
    fi
  else
    echo "Not comparing file ${output_product}"
    compare_result="SKIPPED"
  fi

  # add html breaks to newlines
  compare_output="${compare_output//$'\n'/<br>}"
  update_html_results_file "${compare_result}" "${output_product}" "${expected_product}" "${compare_output}"
done

finalize_html_results_file

# Write the status code to an RC file so the integration test script can pick
# it up.
echo $overall_status > $OUTPUT_DIR/"compare_cal_disp_products.rc"

# Always want to return 0 even if some comparisons failed to avoid error handling
# logic in the PGE
exit 0
