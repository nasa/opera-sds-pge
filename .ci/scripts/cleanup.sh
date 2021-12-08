#!/bin/bash

# Copyright 2021, by the California Institute of Technology.
# ALL RIGHTS RESERVED.
# United States Government sponsorship acknowledged.
# Any commercial use must be negotiated with the Office of Technology Transfer
# at the California Institute of Technology.
# This software may be subject to U.S. export control laws and regulations.
# By accepting this document, the user agrees to comply with all applicable
# U.S. export laws and regulations. User has the responsibility to obtain
# export licenses, or other export authority as may be required, before
# exporting such information to foreign countries or providing access to
# foreign persons.

# Script to clean up Docker images from the CI pipeline instance

# command line args
TAG=$1

# defaults
[ -z "${TAG}" ] && TAG="${USER}-dev"

# Remove docker images with the specified tag
echo "Removing all Docker images with tag ${TAG}..."
for i in {1..2}
do
  docker images | grep ${TAG} | awk '{print $3}' | xargs -r docker rmi -f
  docker images -q --filter "label=org.label-schema.version=${TAG}" | xargs -r docker rmi -f
done
