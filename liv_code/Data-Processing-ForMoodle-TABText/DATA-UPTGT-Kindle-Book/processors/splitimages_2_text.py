#!/usr/bin/env python3
"""
OCR Processor for UPTGT Kindle Book Images
Python 3.14 compatible
"""

from pathlib import Path
from PIL import Image
import pytesseract
import sys


def main():
    # Initialize SCRIPT_DIR
    SCRIPT_DIR = Path(__file__).resolve().parent

    # One level up
    INPUT_DIR = SCRIPT_DIR.parent

    # Images are inside INPUT_DIR/SPLIT
    IMAGE_DIR = INPUT_DIR / "SPLIT"

    # OUTPUT_DIR = INPUT_DIR/SPLIT_2_TEXT
    OUTPUT_DIR = INPUT_DIR / "SPLIT_2_TEXT"

    # Create OUTPUT_DIR if not present
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"SCRIPT_DIR  : {SCRIPT_DIR}")
    print(f"INPUT_DIR   : {INPUT_DIR}")
    print(f"IMAGE_DIR   : {IMAGE_DIR}")
    print(f"OUTPUT_DIR  : {OUTPUT_DIR}")
    print("--------------------------------------------------")

    if not IMAGE_DIR.exists():
        print("SPLIT directory does not exist.")
        sys.exit(1)

    # Load all PNG images containing token
    images = sorted(
        IMAGE_DIR.glob("*UPTGT-Eng-Lit_*.png")
    )

    if not images:
        print("No matching PNG images found.")
        sys.exit(0)

    print(f"Found {len(images)} images to process.\n")

    # Process each image
    for img_path in images:
        print(f"Processing: {img_path.name}")

        try:
            with Image.open(img_path) as img:
                # Perform OCR
                text = pytesseract.image_to_string(img, lang="eng")

            # Create output file path
            output_file = OUTPUT_DIR / f"{img_path.stem}.txt"

            # Save OCR text
            output_file.write_text(text, encoding="utf-8")

            print(f"  Saved: {output_file.name}")

        except Exception as e:
            print(f"  Error processing {img_path.name}: {e}")

    print("\nAll images processed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()