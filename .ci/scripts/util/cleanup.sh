#!/bin/bash

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
