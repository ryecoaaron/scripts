#!/bin/bash

preset="H.265 MKV 1080p30"

# Check if a directory is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <parent_directory>"
  exit 1
fi

# Set the parent directory
PARENT_DIR="$1"

# Check if the directory exists
if [ ! -d "${PARENT_DIR}" ]; then
  echo "Error: Directory ${PARENT_DIR} does not exist."
  exit 1
fi

# Populate an array with all .mkv files in the given directory and subdirectories
mapfile -t mkv_files < <(find "${PARENT_DIR}" -type f -name "*.mkv" | grep -v "_h265")

# Loop through the array and process each file
for file in "${mkv_files[@]}"; do
  output="${file%.mkv}_h265.mkv"
  if [ -f "${output}" ]; then
    echo "${output} already exists. Skipping..."
    continue
  fi
  echo "Processing ${file}..."
  HandBrakeCLI -i "${file}" -o "${output}" \
    -e nvenc_h265 \
    -b 5000 \
    -Z "${preset}" \
    --all-audio \
    --all-subtitles \
    --subtitle-burned=none \
    --subtitle-forced=none

  if [ $? -eq 0 ]; then
    echo "Successfully encoded ${file} to ${output}"
  else
    echo "Failed to encode ${file}"
    exit 2
  fi
done

echo "All files processed."

exit 0
