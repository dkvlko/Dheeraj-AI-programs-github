#!/usr/bin/env python3
"""
Filter text for Moodle import
Python 3.14 compatible
Equivalent to original AWK filtering logic
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

    INPUT_FILE = TEXT_DIR / "UPTGT-Eng-Lit_Combined_Text_9.txt"

    OUTPUT_DIR = TEXT_DIR
    OUTPUT_FILE = OUTPUT_DIR / "UPTGT-Eng-Lit_Combined_Text_9_formoodle.txt"

    # --------------------------------------------------
    # Check input file
    # --------------------------------------------------
    if not INPUT_FILE.exists():
        print("Input file not found.")
        sys.exit(1)

    print(f"SCRIPT_DIR : {SCRIPT_DIR}")
    print(f"INPUT_FILE : {INPUT_FILE}")
    print(f"OUTPUT_FILE: {OUTPUT_FILE}")
    print("--------------------------------------------------")

    output_lines = []

    # --------------------------------------------------
    # Filtering logic (AWK equivalent)
    # --------------------------------------------------
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            # Delete if "=" present
            if "=" in line:
                continue

            # Keep if starts with number.
            if re.match(r'^[0-9]+\.', line):
                output_lines.append(line)
                continue

            # Keep if contains ")"
            if ")" in line:
                output_lines.append(line)
                continue

            # Delete everything else
            continue

    # --------------------------------------------------
    # Write output
    # --------------------------------------------------
    OUTPUT_FILE.write_text(
        "\n".join(output_lines) + "\n",
        encoding="utf-8"
    )

    print("Done.")
    print("Filtered file created:")
    print(OUTPUT_FILE)

    sys.exit(0)


if __name__ == "__main__":
    main()