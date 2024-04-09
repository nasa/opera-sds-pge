#!/bin/bash

# Script used to orchestrate the pair-wise comparison of output and expected
# CSLC_S1 products. Each individual pair of products is compared using the
# dswx_hls_compare.py script.

set -e
umask 002

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
. "$SCRIPT_DIR"/../util/test_int_util.sh

# TODO: add validation that OUTPUT/EXPECTED exist within container
OUTPUT_DIR="/home/compass_user/output_dir"
EXPECTED_DIR="/home/compass_user/expected_output_dir"
PGE_NAME="cslc_s1"

# overall_status values and their meaning
# 0 - pass
# 1 - failure to execute some part of this script
# 2 - product validation failure
overall_status=0

initialize_html_results_file "$OUTPUT_DIR" "$PGE_NAME"
echo "<tr><th>Compare Result</th><th><ul><li>Expected file</li><li>Output file</li></ul></th><th>cslc_s1_compare.py output</th></tr>" >> "$RESULTS_FILE"

declare -a burst_ids=("t064_135518_iw1"
                      "t064_135519_iw1"
                      "t064_135520_iw1"
                      "t064_135521_iw1"
                      "t064_135522_iw1"
                      "t064_135523_iw1"
                      "t064_135524_iw1"
                      "t064_135525_iw1"
                      "t064_135526_iw1"
                      "t064_135527_iw1")

for burst_id in "${burst_ids[@]}"; do
    cslc_compare_result="PENDING"
    expected_output_dir="${TMP_DIR}/${EXPECTED_DIR%.*}/expected_output_s1_cslc"

    echo "-------------------------------------"
    echo "Comparing results for burst id ${burst_id}"

#    burst_id_uppercase=${burst_id^^}
#    burst_id_replace_underscores=${burst_id_uppercase//_/-}
#    burst_id_pattern="OPERA_L2_CSLC-S1_${burst_id_replace_underscores}_*.h5"
#    output_file=`ls $OUTPUT_DIR/$burst_id_pattern`

#    echo "Output CSLC file matching burst id is $output_file"

    ref_product="${expected_output_dir}/${burst_id}/20220501/${burst_id}_20220501.h5"
#    sec_product="${output_file}"
    sec_product=$OUTPUT_DIR/${burst_id}/20220501/${burst_id}_20220501.h5"

    compare_out=$("${SCRIPT_DIR}"/../cslc_s1/cslc_s1_compare.py --ref-product ${ref_product} --sec-product ${sec_product} -p CSLC 2>&1) || compare_exit_status=$?

    echo "$compare_out"
    if [[ "$compare_out" != *"All CSLC product checks have passed"* ]]; then
        echo "Failure: All CSLC product checks DID NOT PASS"
        cslc_compare_result="FAIL"
        overall_status=2
    elif [[ "$compare_out" != *"All CSLC metadata checks have passed"* ]]; then
        echo "Failure: All CSLC metadata checks DID NOT PASS"
        cslc_compare_result="FAIL"
        overall_status=2
    else
        echo "Product validation was successful"
        cslc_compare_result="PASS"
    fi

    compare_out="${compare_out//$'\n'/<br>}"
    update_html_results_file "${cslc_compare_result}" "${ref_product}" "${sec_product}" "${compare_out}"
done

finalize_html_results_file

# Write the status code to an RC file so the integration test script can pick
# it up.
echo $overall_status > $OUTPUT_DIR/"compare_cslc_s1_products.rc"

# Always want to return 0 even if some comparisons failed to avoid error handling
# logic in the PGE
exit 0

