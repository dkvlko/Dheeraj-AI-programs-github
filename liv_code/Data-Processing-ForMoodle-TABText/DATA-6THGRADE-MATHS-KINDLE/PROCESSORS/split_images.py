#!/usr/bin/env python3
"""
Image Splitter for 6th grade Kindle Book Processing
Python 3.14 compatible
"""

from pathlib import Path
from PIL import Image
import sys


def main():
    # Initialize SCRIPT_DIR
    SCRIPT_DIR = Path(__file__).resolve().parent

    # One level up
    INPUT_DIR = SCRIPT_DIR.parent

    # OUTPUT_DIR = INPUT_DIR/SPLIT
    OUTPUT_DIR = INPUT_DIR / "SPLIT"

    # Create SPLIT directory if not present
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"SCRIPT_DIR  : {SCRIPT_DIR}")
    print(f"INPUT_DIR   : {INPUT_DIR}")
    print(f"OUTPUT_DIR  : {OUTPUT_DIR}")
    print("--------------------------------------------------")

    # Load all PNG images containing the token
    images = sorted(
        INPUT_DIR.glob("*6th_GRADE_MATHS_KINDLE_*.png")
    )

    if not images:
        print("No matching PNG images found.")
        sys.exit(0)

    print(f"Found {len(images)} images to process.\n")

    # Process each image
    for img_path in images:
        print(f"Processing: {img_path.name}")

        with Image.open(img_path) as img:
            width, height = img.size

            # Split width into half
            mid = width // 2

            # Define left and right boxes
            left_box = (0, 0, mid, height)
            right_box = (mid, 0, width, height)

            left_img = img.crop(left_box)
            right_img = img.crop(right_box)

            # Generate output filenames
            base_name = img_path.stem
            left_name = f"{base_name}_00.png"
            right_name = f"{base_name}_01.png"

            # Save images
            left_img.save(OUTPUT_DIR / left_name)
            right_img.save(OUTPUT_DIR / right_name)

            print(f"  Saved: {left_name}")
            print(f"  Saved: {right_name}")

    print("\nAll images processed successfully.")
    sys.exit(0)


if __name__ == "__main__":
    main()