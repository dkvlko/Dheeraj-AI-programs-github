#!/bin/bash

INPUT="/home/dkvlko/Pictures/UPTGT/SPLIT/STITCH/UPTGT_Combined_QA_tight_fixed.txt"

DIR="$(dirname "$INPUT")"
FILE="$(basename "$INPUT" .txt)"

OUTPUT="$DIR/${FILE}_formoodle.txt"

if [ ! -f "$INPUT" ]; then
    echo "Input file not found."
    exit 1
fi

awk '
{
    line = $0

    # Delete if "=" present
    if (line ~ /=/) {
        next
    }

    # Keep if starts with number.
    if (line ~ /^[0-9]+\./) {
        print
        next
    }

    # Keep if contains ")"
    if (line ~ /\)/) {
        print
        next
    }

    # Delete everything else
    next
}
' "$INPUT" > "$OUTPUT"

echo "Done."
echo "Filtered file created:"
echo "$OUTPUT"

