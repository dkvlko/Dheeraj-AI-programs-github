#!/bin/bash

# Get script's directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

OUTPUT_DIR="$SCRIPT_DIR/SPLIT"
mkdir -p "$OUTPUT_DIR"

shopt -s nullglob

for img in "$SCRIPT_DIR"/*.png; do

    filename="$(basename "$img")"
    base="${filename%.png}"

    # Skip already processed files inside SPLIT folder
    if [[ "$img" == *"/SPLIT/"* ]]; then
        continue
    fi

    echo "Processing $filename"

    # Get image width
    WIDTH=$(identify -format "%w" "$img")
    HALF_WIDTH=$((WIDTH / 2))

    # Left half
    convert "$img" -crop "${HALF_WIDTH}x+0+0" +repage \
        "$OUTPUT_DIR/${base}_01.png"

    # Right half
    convert "$img" -crop "${HALF_WIDTH}x+${HALF_WIDTH}+0" +repage \
        "$OUTPUT_DIR/${base}_02.png"

done

echo "Done."
