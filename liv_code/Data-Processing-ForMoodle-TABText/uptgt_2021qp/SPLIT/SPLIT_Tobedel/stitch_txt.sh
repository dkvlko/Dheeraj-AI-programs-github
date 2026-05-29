#!/bin/bash

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

OUTPUT_DIR="$SCRIPT_DIR/STITCH"
OUTPUT_FILE="$OUTPUT_DIR/UPTGT_Combined_QA.txt"

mkdir -p "$OUTPUT_DIR"

# Empty the output file first
: > "$OUTPUT_FILE"

echo "Stitching TXT files from:"
echo "$SCRIPT_DIR"
echo

shopt -s nullglob

# Read + sort filenames naturally
files=("$SCRIPT_DIR"/*.txt)

IFS=$'\n' sorted_files=($(printf "%s\n" "${files[@]}" | sort -V))

for file in "${sorted_files[@]}"; do

    filename="$(basename "$file")"

    echo "Appending: $filename"

    echo "===== START: $filename =====" >> "$OUTPUT_FILE"
    cat "$file" >> "$OUTPUT_FILE"
    echo -e "\n===== END: $filename =====\n" >> "$OUTPUT_FILE"

done

echo
echo "Done."
echo "Output file:"
echo "$OUTPUT_FILE"
