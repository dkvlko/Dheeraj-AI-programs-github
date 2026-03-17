#!/usr/bin/env python3
"""
Combine OCR Text Files for UPTGT Kindle Book
Python 3.14 compatible
"""

from pathlib import Path
import sys


def main():
    # Initialize SCRIPT_DIR
    SCRIPT_DIR = Path(__file__).resolve().parent

    # One level up
    INPUT_DIR = SCRIPT_DIR.parent

    # Source directory
    TEXT_DIR = INPUT_DIR / "SPLIT_2_TEXT"

    # Output directory
    OUTPUT_DIR = INPUT_DIR / "COMBINED_TEXT_KINDLE"

    # Create output directory if not present
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"SCRIPT_DIR : {SCRIPT_DIR}")
    print(f"INPUT_DIR  : {INPUT_DIR}")
    print(f"TEXT_DIR   : {TEXT_DIR}")
    print(f"OUTPUT_DIR : {OUTPUT_DIR}")
    print("--------------------------------------------------")

    if not TEXT_DIR.exists():
        print("SPLIT_2_TEXT directory does not exist.")
        sys.exit(1)

    # Load all matching txt files and sort them by name
    text_files = sorted(
        TEXT_DIR.glob("*UPTGT-Eng-Lit_*.txt")
    )

    if not text_files:
        print("No matching text files found.")
        sys.exit(0)

    print(f"Found {len(text_files)} text files.\n")

    # Output file path
    combined_file_path = OUTPUT_DIR / "UPTGT-Eng-Lit_Combined_Text.txt"

    # Open combined file in write mode (overwrite if exists)
    with combined_file_path.open("w", encoding="utf-8") as combined_file:

        for txt_path in text_files:
            print(f"Appending: {txt_path.name}")

            content = txt_path.read_text(encoding="utf-8")

            combined_file.write(content)
            combined_file.write("\n\n")  # Optional separation between files

    print(f"\nCombined file saved as: {combined_file_path.name}")
    print("Process completed successfully.")

    sys.exit(0)


if __name__ == "__main__":
    main()