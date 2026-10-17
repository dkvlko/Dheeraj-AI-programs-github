#!/usr/bin/env python3
# Python 3.14 compatible

from pathlib import Path
import re

# Input and output files
M1_PATH = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Prka_1WSubs/COMBINED_TEXT/OWSubs_Comb.txt"
)

OUTPUT_PATH = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Prka_1WSubs/COMBINED_TEXT/OWSubs_Comb_up1.txt"
)

# Opt identifier pattern:
# "(" + any single character + ")"
# Examples: (a), (b), (1), (A)
OPT_PATTERN = re.compile(r"\(.\)")


def insert_newlines_before_options(line: str) -> str:
    """
    Inserts a newline before every Opt identifier
    except the first occurrence in the line.
    """

    matches = list(OPT_PATTERN.finditer(line))

    # If fewer than 2 Opt identifiers exist,
    # no modification required
    if len(matches) < 2:
        return line

    result = []
    last_pos = 0

    for index, match in enumerate(matches):

        start = match.start()

        # From second Opt onward,
        # insert newline before Opt
        if index >= 1:
            result.append(line[last_pos:start])
            result.append("\n")
            last_pos = start

    result.append(line[last_pos:])

    return "".join(result)


def process_mcq_file():

    # Load M1 into memory (Mcq1)
    with M1_PATH.open("r", encoding="utf-8") as f:
        mcq1_lines = f.readlines()

    processed_lines = []

    # Process line-by-line
    for line in mcq1_lines:

        line = line.rstrip("\n")

        updated_line = insert_newlines_before_options(line)

        processed_lines.append(updated_line)

    # Save final output
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        f.write("\n".join(processed_lines))

    print("Processing completed.")
    print(f"Output saved to:\n{OUTPUT_PATH}")


if __name__ == "__main__":
    process_mcq_file()
