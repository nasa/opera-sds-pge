#!/bin/bash

compare_secrets() {
  diff <(jq -r '.results | keys[] as $key | "\($key),\(.[$key] | .[] | .hashed_secret)"' "${1}" | sort) <(jq -r '.results | keys[] as $key | "\\($key),\\(.[$key] | .[] | .hashed_secret)"' "${2}" | sort) | grep -q '>' ;
}
