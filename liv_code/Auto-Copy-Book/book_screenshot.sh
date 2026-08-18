#!/bin/bash

SAVE_DIR="/data/BLOBS/Kindle_Naxal"
PREFIX="Kindle_Naxal_"

mkdir -p "$SAVE_DIR"

# Find last number used (NUMERICALLY correct)
last_file=$(ls "$SAVE_DIR"/${PREFIX}*.png 2>/dev/null | sort -V | tail -n 1)

if [ -z "$last_file" ]; then
    next_number=1
else
    last_number=$(basename "$last_file" | sed -E "s/${PREFIX}([0-9]+)\.png/\1/")
    next_number=$((10#$last_number + 1))
fi

# Use fixed width numbering (recommended: 4 digits)
printf -v formatted "%04d" "$next_number"

gnome-screenshot -f "$SAVE_DIR/${PREFIX}${formatted}.png"
