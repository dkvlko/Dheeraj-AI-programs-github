#!/bin/bash

INPUT="/home/dkvlko/Pictures/UPTGT/SPLIT/STITCH/UPTGT_Combined_QA_tight.txt"

DIR="$(dirname "$INPUT")"
FILE="$(basename "$INPUT" .txt)"

OUTPUT="$DIR/${FILE}_fixed.txt"

awk '
{
    lines[NR] = $0
}

END {

    i = 1

    while (i <= NR) {

        line = lines[i]

        # Check if line starts with number.
        if (line ~ /^[0-9]+\./) {

            nextline = lines[i+1]

            # If next line exists
            if (i+1 <= NR) {

                # If next line does NOT contain ")"
                if (nextline !~ /\)/) {

                    merged = line " " nextline
                    print merged

                    i += 2
                    continue
                }
            }
        }

        print line
        i++
    }
}
' "$INPUT" > "$OUTPUT"

echo "Done."
echo "Output:"
echo "$OUTPUT"
