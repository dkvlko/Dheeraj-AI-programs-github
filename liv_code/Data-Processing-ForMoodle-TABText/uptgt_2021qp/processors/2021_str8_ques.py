#!/usr/bin/env python3
# Python 3.14

import re

input_file = "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Prka_PQ2021/COMB_TEXT/UPTGT2021-Combined_up1.txt"

output_file = "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Prka_PQ2021/COMB_TEXT/UPTGT2021-Combined_up2.txt"

# Regex:
# begins with optional spaces + number
number_start_re = re.compile(r'^\s*\d+')

# remove tokens like 4.  6.  125.
number_dot_re = re.compile(r'\b\d+\.\s*')

# begins with:
# (
#  (
#   (
# OR number
valid_start_re = re.compile(r'^\s*\(|^\s*\d+')


def clean_numbered_line(line: str, sno: int) -> str:
    """
    Remove all number-dot tokens and prefix with sno.
    """
    line = number_dot_re.sub('', line)
    line = line.strip()
    return f"{sno}. {line}"


def main():
    sno = 0
    output_lines = []

    with open(input_file, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # If line begins with number
        if number_start_re.match(line):
            sno += 1
            current_line = clean_numbered_line(line, sno)

        else:
            current_line = line

        i += 1

        # Append following lines that DO NOT begin with
        # "(" or number
        while i < len(lines):
            next_line_raw = lines[i]
            next_line = next_line_raw.strip()

            # Skip empty lines
            if not next_line:
                i += 1
                continue

            # Stop merging if next line begins with "(" or number
            if valid_start_re.match(next_line_raw):
                break

            # Otherwise append to current line
            current_line += " " + next_line
            i += 1

        output_lines.append(current_line)

    with open(output_file, "w", encoding="utf-8") as f:
        for line in output_lines:
            f.write(line + "\n")

    print("Processing completed.")
    print(f"Output written to:\n{output_file}")


if __name__ == "__main__":
    main()
