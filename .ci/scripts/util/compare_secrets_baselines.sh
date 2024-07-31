#!/bin/bash

compare_secrets() {
  jq -r '.results | keys[] as $key | "\($key),\(.[$key] | .[] | .hashed_secret)"' "${1}" | sort > /data/tmp/.secrets.1
  jq -r '.results | keys[] as $key | "\($key),\(.[$key] | .[] | .hashed_secret)"' "${2}" | sort > /data/tmp/.secrets.2

  diff /data/tmp/.secrets.1 /data/tmp/.secrets.2 > .secrets.diff

  rm -f /data/tmp/.secrets.1 /data/tmp/.secrets.2

  grep -q '>' < .secrets.diff

  # This causes a syntax issue in the pipeline...
  # diff <(jq -r '.results | keys[] as $key | "\($key),\(.[$key] | .[] | .hashed_secret)"' "${1}" | sort) <(jq -r '.results | keys[] as $key | "\($key),\(.[$key] | .[] | .hashed_secret)"' "${2}" | sort) | grep -q '>' ;
}
