#!/usr/bin/env python3
"""
Remove empty / whitespace-only lines from
UPTGT-Eng-Lit_Combined_Text.txt

Python 3.14 compatible
"""

from pathlib import Path


def main():
    # --------------------------------------------------
    # 1. Define SCRIPT_DIR
    # --------------------------------------------------
    SCRIPT_DIR = Path(__file__).resolve().parent

    # --------------------------------------------------
    # 2. Define INPUT_DIR (one level up)
    # --------------------------------------------------
    INPUT_DIR = SCRIPT_DIR.parent

    # --------------------------------------------------
    # 3. Define directories and files
    # --------------------------------------------------
    COMBINED_DIR = INPUT_DIR / "COMBINED_TEXT_KINDLE"

    INPUT_FILE = COMBINED_DIR / "UPTGT-Eng-Lit_Combined_Text.txt"

    OUTPUT_DIR = COMBINED_DIR
    OUTPUT_FILE = OUTPUT_DIR / "UPTGT-Eng-Lit_Combined_Text_tighten.txt"

    # --------------------------------------------------
    # 4. Validate input file
    # --------------------------------------------------
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found:\n{INPUT_FILE}")

    print(f"Reading file: {INPUT_FILE}")

    # --------------------------------------------------
    # 5. Process lines
    # Remove empty or whitespace-only lines
    # --------------------------------------------------
    cleaned_lines = []

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():  # keeps only non-empty content
                cleaned_lines.append(line.rstrip() + "\n")

    # --------------------------------------------------
    # 6. Save output
    # --------------------------------------------------
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        f.writelines(cleaned_lines)

    print(f"Output written to: {OUTPUT_FILE}")
    print(f"Total lines kept: {len(cleaned_lines)}")


# ------------------------------------------------------
# Entry point
# ------------------------------------------------------
if __name__ == "__main__":
    main()