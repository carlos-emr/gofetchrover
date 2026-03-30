#!/bin/bash

# URL of the JDK
JDK_URL="https://builds.openlogic.com/downloadJDK/openlogic-openjdk/8u422-b05/openlogic-openjdk-8u422-b05-linux-x32-deb.deb"

# Target download directory
TARGET_DIR="./Docker/builder/jdk"

# Create the directory if it doesn't exist
mkdir -p "$TARGET_DIR"

# Output file path
OUTPUT_FILE="$TARGET_DIR/openlogic-openjdk-8u422-b05-linux-x32.deb"

# Check if file already exists
if [ -f "$OUTPUT_FILE" ]; then
    echo "File already exists: $OUTPUT_FILE"
    echo "Skipping download."
else
    echo "Downloading JDK to $OUTPUT_FILE..."
    wget -O "$OUTPUT_FILE" "$JDK_URL"
    if [ $? -ne 0 ] || [ ! -s "$OUTPUT_FILE" ]; then
        echo "Download failed!"
        rm -f "$OUTPUT_FILE"
        exit 1
    fi
    echo "Download completed."
fi