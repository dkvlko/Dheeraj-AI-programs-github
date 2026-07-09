#!/usr/bin/env python3
"""
MCQ Screenshot Collector
Python 3.14
Ubuntu Noble compatible

Workflow:
1. Detect latest numeric prefix from existing qtext PNG files.
2. Ask user whether to proceed with a new question.
3. Guide user to take screenshots in strict order.
4. Detect latest screenshots from Screenshot folder.
5. Ask which screenshots were actually taken.
6. For missing options A/B/C/D, collect typed text instead.
7. Rename and move files into appropriate folders.

Author: ChatGPT
"""

from __future__ import annotations

import shutil
import time
from datetime import datetime
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(
    "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Krish_Maths4/IMG_QS/SETA_1"
)

SCREENSHOT_DIR = Path("/home/dkvlko/Pictures/Screenshots")

VARIABLES = [
    "qtext",
    "qimage",
    "qopta",
    "qoptb",
    "qoptc",
    "qoptd",
]

# ============================================================
# HELPERS
# ============================================================


def yes_no(prompt: str) -> bool:
    """Ask yes/no question."""
    while True:
        ans = input(f"{prompt} (yes/no): ").strip().lower()

        if ans in ["yes", "y"]:
            return True

        if ans in ["no", "n"]:
            return False

        print("Please enter yes or no.")


def get_next_prefix() -> str:
    """
    Look inside qtext folder for files like:
    001-qtext.png

    Return next prefix as 3 digit string.
    """

    qtext_dir = BASE_DIR / "qtext"
    qtext_dir.mkdir(parents=True, exist_ok=True)

    matched_numbers = []

    for file in qtext_dir.glob("*.png"):
        name = file.name

        # expected format: ddd-qtext.png
        if len(name) >= 13 and name.endswith("-qtext.png"):
            prefix = name[:3]

            if prefix.isdigit():
                matched_numbers.append(int(prefix))

    if not matched_numbers:
        return "001"

    latest = max(matched_numbers)

    return f"{latest + 1:03d}"


def wait_countdown(seconds: int):
    """Simple countdown."""
    for i in range(seconds, 0, -1):
        print(f"Starting in {i}...")
        time.sleep(1)


def get_latest_screenshots(n: int) -> list[Path]:
    """
    Fetch last N modified screenshots.
    Return oldest-first among those N.
    """

    screenshots = list(SCREENSHOT_DIR.glob("*.png"))

    if len(screenshots) < n:
        raise RuntimeError(
            f"Only {len(screenshots)} screenshots found, but {n} required."
        )

    screenshots.sort(key=lambda p: p.stat().st_mtime)

    latest_n = screenshots[-n:]

    # oldest first
    latest_n.sort(key=lambda p: p.stat().st_mtime)

    return latest_n


def save_text_option(variable_name: str, text: str) -> Path:
    """
    Save typed option text temporarily.
    """

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    temp_file = Path(f"{variable_name}-{timestamp}.txt")

    temp_file.write_text(text, encoding="utf-8")

    return temp_file


def move_and_rename(src: Path, variable_name: str, prefix: str):
    """
    Rename and move file into:
    BASE_DIR/variable_name/
    """

    target_dir = BASE_DIR / variable_name
    target_dir.mkdir(parents=True, exist_ok=True)

    extension = src.suffix

    target_name = f"{prefix}-{variable_name}{extension}"

    destination = target_dir / target_name

    shutil.move(str(src), str(destination))

    print(f"Saved: {destination}")


# ============================================================
# MAIN
# ============================================================

def main():


    print("\n==============================")
    print("MCQ Screenshot Collector")
    print("==============================\n")

    fileprefix = get_next_prefix()

    print(f"Next file prefix = {fileprefix}")

    #proceed = yes_no("Would you like to proceed with a new question?")

    #if not proceed:
    #    print("Exiting.")
    #    return

    print("\nTake screenshots STRICTLY in this order:")
    print("1. Question text area")
    print("2. Question image area")
    print("3. Option A")
    print("4. Option B")
    print("5. Option C")
    print("6. Option D")

    print("\nYou will now get 3 seconds before starting.")

    wait_countdown(3)

    input(
        "\nPress ENTER when you have COMPLETED taking all desired screenshots..."
    )

    proceed2 = yes_no("Have you finished taking screenshots and should we proceed?")

    if not proceed2:
        print("Cancelled.")
        return

    # --------------------------------------------------------
    # Collect yes/no status
    # --------------------------------------------------------

    screensh = {
        "qtext": 0,
        "qimage": 0,
        "qopta": 0,
        "qoptb": 0,
        "qoptc": 0,
        "qoptd": 0,
    }

    questions = {
        "qtext": "Did you take screenshot of question text area?",
        "qimage": "Did you take screenshot of question image area?",
        "qopta": "Did you take screenshot of option A?",
        "qoptb": "Did you take screenshot of option B?",
        "qoptc": "Did you take screenshot of option C?",
        "qoptd": "Did you take screenshot of option D?",
    }

    for var in VARIABLES:
        screensh[var] = 1 if yes_no(questions[var]) else 0

    # --------------------------------------------------------
    # Count screenshots
    # --------------------------------------------------------

    total_images = sum(screensh.values())

    print(f"\nTotal screenshots expected = {total_images}")

    latest_images = []

    if total_images > 0:
        latest_images = get_latest_screenshots(total_images)

    # --------------------------------------------------------
    # Populate actual file mapping
    # --------------------------------------------------------

    final_files = {}

    image_index = 0

    for var in VARIABLES:

        if screensh[var] == 1:

            final_files[var] = latest_images[image_index]

            image_index += 1

        else:

            # only for missing options A/B/C/D
            if var in ["qopta", "qoptb", "qoptc", "qoptd"]:

                text = input(f"Enter text for {var}: ").strip()

                temp_txt = save_text_option(var, text)

                final_files[var] = temp_txt

    # --------------------------------------------------------
    # Move and rename
    # --------------------------------------------------------

    print("\nProcessing files...\n")

    for var, src_file in final_files.items():

        move_and_rename(src_file, var, fileprefix)

    print("\nDone.")
    print(f"Question saved with prefix {fileprefix}")


# ============================================================

if __name__ == "__main__":
    while True:
        proceed = yes_no("\nWould you like to proceed with a new question")

        if not proceed:
            print("Exiting.")
            break
        main()
