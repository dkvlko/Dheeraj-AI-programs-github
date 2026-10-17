#!/usr/bin/env python3
"""
Equivalent Python version of AWK merge-line script
Python 3.14 compatible
"""

from pathlib import Path
import re
import sys


def main():
    # --------------------------------------------------
    # Initialize directories
    # --------------------------------------------------
    SCRIPT_DIR = Path(__file__).resolve().parent
    INPUT_DIR = SCRIPT_DIR.parent

    TEXT_DIR = INPUT_DIR / "COMBINED_TEXT_KINDLE"

    INPUT_FILE = TEXT_DIR / "UPTGT-Eng-Lit_Combined_Text_tighten.txt"

    # Output directory = INPUT_DIR (same)
    OUTPUT_DIR = TEXT_DIR

    if not INPUT_FILE.exists():
        print("Input file not found.")
        sys.exit(1)

    OUTPUT_FILE = OUTPUT_DIR / "UPTGT-Eng-Lit_Combined_Text_mergedline.txt"

    print(f"SCRIPT_DIR : {SCRIPT_DIR}")
    print(f"INPUT_DIR  : {INPUT_DIR}")
    print(f"INPUT_FILE : {INPUT_FILE}")
    print(f"OUTPUT_FILE: {OUTPUT_FILE}")
    print("--------------------------------------------------")

    # --------------------------------------------------
    # Read all lines (equivalent to awk array lines[NR])
    # --------------------------------------------------
    lines = INPUT_FILE.read_text(encoding="utf-8").splitlines()

    merged_output = []

    i = 0
    total_lines = len(lines)

    # --------------------------------------------------
    # Equivalent to awk while (i <= NR)
    # --------------------------------------------------
    while i < total_lines:

        line = lines[i]

        # CONDITION 1:
        # line starts with number + dot
        if re.match(r'^[0-9]+\.', line):

            # CONDITION 2:
            # next line exists
            if i + 1 < total_lines:
                nextline = lines[i + 1]

                # CONDITION 3:
                # next line does NOT contain ")"
                if not re.search(r'\)', nextline):

                    merged = line + " " + nextline
                    merged_output.append(merged)

                    i += 2
                    continue

        # Default behaviour (print line)
        merged_output.append(line)
        i += 1

    # --------------------------------------------------
    # Write output file
    # --------------------------------------------------
    OUTPUT_FILE.write_text(
        "\n".join(merged_output) + "\n",
        encoding="utf-8"
    )

    print("Processing completed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()