#!/bin/bash

compare_secrets() {
#  jq -r '.results | keys[] as $key | "\($key),\(.[$key] | .[] | .hashed_secret)"' "${1}" | sort > /data/tmp/.secrets.1
#  jq -r '.results | keys[] as $key | "\($key),\(.[$key] | .[] | .hashed_secret)"' "${2}" | sort > /data/tmp/.secrets.1


  diff <(jq -r '.results | keys[] as $key | "\($key),\(.[$key] | .[] | .hashed_secret)"' "${1}" | sort) <(jq -r '.results | keys[] as $key | "\($key),\(.[$key] | .[] | .hashed_secret)"' "${2}" | sort) | grep -q '>' ;
}
