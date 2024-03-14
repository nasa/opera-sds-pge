#!/bin/bash

set -e
umask 002

# Compare and validate the results for different burst IDs, then log the results
# Usage: compare_cslc_s1_products.sh <output_dir> <static_output_dir> <expected_data_zip> <PGE_IMAGE> <PGE_TAG> <RESULTS_FILE>

# Arguments
output_dir=$1
static_output_dir=$2
EXPECTED_DATA=$3
PGE_IMAGE=$4
PGE_TAG=$5
RESULTS_FILE=$6

TMP_DIR=$(mktemp -d)

echo "<tr><th>Compare Result</th><th><ul><li>Expected file</li><li>Output file</li></ul></th><th>validate_product.py output</th></tr>" >> "$RESULTS_FILE"

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
    expected_dir="${TMP_DIR}/${EXPECTED_DATA%.*}/expected_output_s1_cslc"

    echo "-------------------------------------"
    echo "Comparing results for burst id ${burst_id}"

    burst_id_uppercase=${burst_id^^}
    burst_id_replace_underscores=${burst_id_uppercase//_/-}
    burst_id_pattern="OPERA_L2_CSLC-S1_${burst_id_replace_underscores}_*.h5"
    output_file=`ls $output_dir/$burst_id_pattern`

    echo "Output CSLC file matching burst id is $output_file"

    ref_product="/exp/${burst_id}/20220501/${burst_id}_20220501.h5"
    sec_product="/out/$(basename ${output_file})"

    docker_out=$(docker run --rm -u compass_user:compass_user \
                            -v "${TMP_DIR}":/working:ro \
                            -v "${output_dir}":/out:ro \
                            -v "${expected_dir}":/exp:ro \
                            --entrypoint /home/compass_user/miniconda3/envs/COMPASS/bin/python3 \
                            ${PGE_IMAGE}:"${PGE_TAG}" \
                            /working/validate_product.py \
                            --ref-product ${ref_product} \
                            --sec-product ${sec_product} \
                            -p CSLC 2>&1) || docker_exit_status=$?

    echo "$docker_out"
    if [[ "$docker_out" != *"All CSLC product checks have passed"* ]]; then
        echo "Failure: All CSLC product checks DID NOT PASS"
        cslc_compare_result="FAIL"
        overall_status=2
    elif [[ "$docker_out" != *"All CSLC metadata checks have passed"* ]]; then
        echo "Failure: All CSLC metadata checks DID NOT PASS"
        cslc_compare_result="FAIL"
        overall_status=2
    else
        echo "Product validation was successful"
        cslc_compare_result="PASS"
    fi

    docker_out="${docker_out//$'\n'/<br>}"
    echo "<tr><td>${cslc_compare_result}</td><td><ul><li>${ref_product}</li><li>${sec_product}</li></ul></td><td>${docker_out}</td></tr>" >> "$RESULTS_FILE"

done

rm -rf "${TMP_DIR}"