#!/bin/bash

# Script used to orchestrate the pairwise comparison of output and expected
# DIST-S1 products. Each individual pair of products is compared using the
# dist_s1_compare.py script.

set -e
umask 002

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/../util/test_int_util.sh

OUTPUT_DIR="/home/ops/output_dir"
EXPECTED_DIR="/home/ops/expected_output_dir"
PGE_NAME="dist_s1"

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

echo "<tr><th>Compare Result</th><th><ul><li>Output file</li><li>Expected file</li></ul></th><th>dist_s1_compare.py output</th></tr>" >> "$RESULTS_FILE"

# overall_status values and their meaning
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

for output_product in $(find $OUTPUT_DIR -maxdepth 1 -mindepth 1 -type d)
do
  compare_output="N/A"
  compare_result="N/A"
  expected_product="N/A"

  echo "output_product $output_product"
  output_product=$(basename -- "$output_product")

  # Parse the tile code from the filename
  IFS='_' read -ra ARR <<< "$output_product"
  tile_code=${ARR[3]}

  for potential_product in $(find $EXPECTED_DIR -maxdepth 1 -mindepth 1 -type d)
  do
    if [[ "$potential_product" == *"$tile_code"* ]]; then
      echo "expected product is $potential_product"
      expected_product=$potential_product
      break
    fi
  done

  if [ ! -d "$expected_product" ]; then
    echo "No matching product found in expected directory $EXPECTED_DIR"
    overall_status=1
    compare_result="FAIL"
    compare_output="FAILED"
  else
     # compare output and expected files
     echo "python3 dist_s1_compare.py $(basename -- ${expected_product}) ${output_product}"
     compare_output=$(python3 $SCRIPT_DIR/dist_s1_compare.py ${expected_product} $OUTPUT_DIR/${output_product})
     echo "$compare_output"
  fi

  if [[ "$compare_output" != *"FAIL"* ]]; then
      echo "Product validation was successful for $output_product"
      compare_result="PASS"
  else
      echo "Failure: Some comparisons failed for $output_product"
      compare_result="FAIL"
      overall_status=2
  fi

  # add html breaks to newlines
  compare_output=${compare_output//$'\n'/<br>$'\n'}

  update_html_results_file "${compare_result}" "${output_product}" "$(basename -- "$expected_product")" "${compare_output}"
done

finalize_html_results_file

# Write the status code to an RC file so the integration test script can pick it up.
# shellcheck disable=SC1073
echo $overall_status > $OUTPUT_DIR/"compare_dist_s1_products.rc"

# Always want to return 0 even if some comparisons failed to avoid error handling logic in the PGE
exit 0
