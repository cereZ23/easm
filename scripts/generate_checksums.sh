#!/bin/bash
# Script to generate SHA256 checksums for ProjectDiscovery tools
# This script downloads the tools and generates their checksums for use in Dockerfile

set -euo pipefail

TEMP_DIR=$(mktemp -d)
echo "Working directory: $TEMP_DIR"
cd "$TEMP_DIR"

# Define tool versions
declare -A TOOLS
TOOLS[subfinder]="2.6.3"
TOOLS[dnsx]="1.2.1"
TOOLS[httpx]="1.3.7"
TOOLS[naabu]="2.2.0"
TOOLS[katana]="1.0.5"
TOOLS[nuclei]="3.1.5"
TOOLS[tlsx]="1.1.5"
TOOLS[uncover]="1.0.7"
TOOLS[notify]="1.0.5"

echo "Downloading tools and generating checksums..."
echo ""
echo "Copy these values into Dockerfile.worker.secure:"
echo "================================================"
echo ""

for tool in "${!TOOLS[@]}"; do
    version="${TOOLS[$tool]}"
    url="https://github.com/projectdiscovery/${tool}/releases/download/v${version}/${tool}_${version}_linux_amd64.zip"

    echo "Downloading ${tool} v${version}..."

    if wget -q "$url" -O "${tool}.zip" 2>/dev/null; then
        sha256=$(sha256sum "${tool}.zip" | cut -d' ' -f1)

        echo "ARG ${tool^^}_VERSION=${version}"
        echo "ARG ${tool^^}_SHA256=${sha256}"
        echo ""

        rm "${tool}.zip"
    else
        echo "ERROR: Failed to download ${tool}"
        echo ""
    fi
done

# Handle Amass separately (different URL pattern)
echo "Downloading amass..."
amass_version="4.2.0"
amass_url="https://github.com/owasp-amass/amass/releases/download/v${amass_version}/amass_Linux_amd64.zip"

if wget -q "$amass_url" -O "amass.zip" 2>/dev/null; then
    sha256=$(sha256sum "amass.zip" | cut -d' ' -f1)

    echo "ARG AMASS_VERSION=${amass_version}"
    echo "ARG AMASS_SHA256=${sha256}"
    echo ""

    rm "amass.zip"
else
    echo "ERROR: Failed to download amass"
    echo ""
fi

echo "================================================"
echo ""
echo "Checksums generated successfully!"
echo "Update Dockerfile.worker.secure with these values."
echo ""

# Cleanup
cd - > /dev/null
rm -rf "$TEMP_DIR"
echo "Cleaned up temporary files."