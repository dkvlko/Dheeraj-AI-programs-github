#!/bin/bash

INPUT="/home/dkvlko/Pictures/UPTGT/SPLIT/STITCH/UPTGT_Combined_QA.txt"

DIR="$(dirname "$INPUT")"
FILE="$(basename "$INPUT" .txt)"

OUTPUT="$DIR/${FILE}_tight.txt"

if [ ! -f "$INPUT" ]; then
    echo "Input file not found."
    exit 1
fi

# Remove empty / whitespace-only lines
grep -v '^[[:space:]]*$' "$INPUT" > "$OUTPUT"

echo "Done."
echo "Output file created:"
echo "$OUTPUT"
