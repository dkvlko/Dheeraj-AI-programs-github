#!/usr/bin/env python3

from pathlib import Path
import re
import shutil
import time

# =========================================================
# CONFIGURATION
# =========================================================

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

# =========================================================
# CREATE DESTINATION DIRECTORIES
# =========================================================

for var in VARIABLES:
    (BASE_DIR / var).mkdir(parents=True, exist_ok=True)

# =========================================================
# FIND LARGEST EXISTING PREFIX
# =========================================================

def get_next_prefix():
    qtext_dir = BASE_DIR / "qtext"

    pattern = re.compile(r"^(\d{3})-qtext\.png$")

    prefixes = []

    for file in qtext_dir.glob("*.png"):
        match = pattern.match(file.name)
        if match:
            prefixes.append(int(match.group(1)))

    if not prefixes:
        return 1

    return max(prefixes) + 1


# =========================================================
# YES/NO INPUT
# =========================================================

def ask_yes_no(question):
    while True:
        ans = input(f"{question} (yes/no): ").strip().lower()

        if ans in ["yes", "y"]:
            return True

        if ans in ["no", "n"]:
            return False

        print("Please answer yes or no.")


# =========================================================
# GET LAST N SCREENSHOTS
# =========================================================

def get_last_n_screenshots(n):
    png_files = list(SCREENSHOT_DIR.glob("*.png"))

    if len(png_files) < n:
        raise RuntimeError(
            f"Only {len(png_files)} screenshots found, but {n} required."
        )

    # Sort by modification time ascending
    png_files.sort(key=lambda f: f.stat().st_mtime)

    # Take latest N
    latest_n = png_files[-n:]

    # Oldest first among selected
    latest_n.sort(key=lambda f: f.stat().st_mtime)

    return latest_n


# =========================================================
# MAIN LOOP
# =========================================================

while True:

    proceed = ask_yes_no("\nWould you like to proceed with a new question")

    if not proceed:
        print("Exiting.")
        break

    fileprefix = get_next_prefix()

    prefix_str = f"{fileprefix:03d}"

    print("\n=================================================")
    print(f"Current question prefix: {prefix_str}")
    print("=================================================\n")

    print("Please take screenshots in STRICT ORDER:")
    print("1. Question text")
    print("2. Question image")
    print("3. Option A")
    print("4. Option B")
    print("5. Option C")
    print("6. Option D")
    print()

    print("You have 3 seconds before starting...")
    time.sleep(3)

    finished = ask_yes_no(
        "Have you finished taking screenshots and want to proceed"
    )

    if not finished:
        print("Skipping this question.")
        continue

    screensh = {}

    screensh["qtext"] = ask_yes_no(
        "Did you take screenshot of question text area"
    )

    screensh["qimage"] = ask_yes_no(
        "Did you take screenshot of question image area"
    )

    screensh["qopta"] = ask_yes_no(
        "Did you take screenshot of option A"
    )

    screensh["qoptb"] = ask_yes_no(
        "Did you take screenshot of option B"
    )

    screensh["qoptc"] = ask_yes_no(
        "Did you take screenshot of option C"
    )

    screensh["qoptd"] = ask_yes_no(
        "Did you take screenshot of option D"
    )

    enabled_vars = [
        var for var in VARIABLES if screensh[var]
    ]

    total_images = len(enabled_vars)

    print(f"\nTotal screenshots expected: {total_images}")

    try:
        latest_images = get_last_n_screenshots(total_images)

    except Exception as e:
        print(f"\nERROR: {e}")
        continue

    # =====================================================
    # MAP FILES TO VARIABLES
    # =====================================================

    file_mapping = {}

    for var, img_path in zip(enabled_vars, latest_images):
        file_mapping[var] = img_path

    # =====================================================
    # COPY + RENAME
    # =====================================================

    print("\nProcessing files...\n")

    for var in VARIABLES:

        if var not in file_mapping:
            continue

        src = file_mapping[var]

        new_name = f"{prefix_str}-{var}.png"

        dest = BASE_DIR / var / new_name

        shutil.copy2(src, dest)

        print(f"{src.name}  -->  {dest}")

    print("\nDone.\n")
