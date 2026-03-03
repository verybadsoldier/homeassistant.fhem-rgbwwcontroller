#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

VERSION=$1

# Ensure a version number was provided
if [ -z "$VERSION" ]; then
  echo "Usage: ./release.sh <version> (e.g., ./release.sh 0.9.1)"
  exit 1
fi

# Update manifest.json in the correct directory (requires jq)
MANIFEST_PATH="custom_components/fhem_rgbwwcontroller/manifest.json"
echo "Updating manifest.json to version $VERSION..."
jq --arg v "$VERSION" '.version = $v' $MANIFEST_PATH > manifest_tmp.json
mv manifest_tmp.json $MANIFEST_PATH

# Stage and commit the changed manifest
git add $MANIFEST_PATH
git commit -m "chore: bump version to $VERSION"

# Create the tag with the 'v' prefix
git tag "v$VERSION"

# Push the commit and the tag to GitHub
echo "Pushing commit and tag to origin..."
git push origin main
git push origin "v$VERSION"

echo "Release v$VERSION successfully pushed!"