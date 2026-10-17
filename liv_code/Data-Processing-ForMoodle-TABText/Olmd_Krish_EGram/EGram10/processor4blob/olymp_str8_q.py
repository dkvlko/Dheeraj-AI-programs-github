#!/usr/bin/env python3

from pathlib import Path
import re

INPUT_FILE = Path(
    "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Krish_Maths4/pdfimgs/COMBINED_TEXT/OlympiadMaths_Set1.txt"
)

OUTPUT_FILE = Path(
    "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Krish_Maths4/pdfimgs/COMBINED_TEXT/OlympiadMaths_Set1_up1.txt"
)

# Token Q:
# Examples:
# 1)
# 2)
# 15)
Q_PATTERN = re.compile(r'^\s*\d+\)')

# Token O:
# Examples:
# A.
# B.
# C.
# D.
O_PATTERN = re.compile(r'^\s*[A-D]\.')

def has_q(line: str) -> bool:
    return bool(Q_PATTERN.match(line))


def has_o(line: str) -> bool:
    return bool(O_PATTERN.match(line))


def main():
    lines = INPUT_FILE.read_text(encoding="utf-8").splitlines()

    output_lines = []

    i = 0
    n = len(lines)

    while i < n:
        current_line = lines[i].strip()

        # If line starts with Q, start merging
        if has_q(current_line):

            merged_line = current_line
            i += 1

            # Merge lines until O token is found
            while i < n:
                next_line = lines[i].strip()

                # Stop merging when O token appears
                if has_o(next_line):
                    break

                # Merge non-empty lines
                if next_line:
                    merged_line += " " + next_line

                i += 1

            # Save merged question line
            output_lines.append(merged_line)

            # From here onward, copy lines as-is
            # until next Q token is found
            while i < n:
                raw_line = lines[i]

                # If next question begins, stop this loop
                if has_q(raw_line.strip()):
                    break

                output_lines.append(raw_line)
                i += 1

        else:
            # Normal line, copy as-is
            output_lines.append(lines[i])
            i += 1

    # Save output file
    OUTPUT_FILE.write_text(
        "\n".join(output_lines),
        encoding="utf-8"
    )

    print(f"Processed file saved to:\n{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
