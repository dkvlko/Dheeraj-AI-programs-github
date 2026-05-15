from pathlib import Path
import re

INPUT_FILE = Path(
    "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Krish_Maths4/pdfimgs/COMBINED_TEXT/OlympiadMaths_Set1_up3.txt"
)

OUTPUT_FILE = Path(
    "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Krish_Maths4/pdfimgs/COMBINED_TEXT/OlympiadMaths_Set1_up4.txt"
)

# Qs token:
# Matches lines beginning with something like:
# 1)
# 10)
# 245)
qs_pattern = re.compile(r"^(\s*)(\d+)\)")

# Op token:
# Matches lines beginning with:
# A.
# B.
# C.
# D.
op_pattern = re.compile(r"^(\s*)([ABCD])\.")

# Mapping for options
option_map = {
    "A": "(a)",
    "B": "(b)",
    "C": "(c)",
    "D": "(d)",
}

output_lines = []

with INPUT_FILE.open("r", encoding="utf-8") as f:
    for line in f:
        # Replace Qs token
        qs_match = qs_pattern.match(line)

        if qs_match:
            spaces = qs_match.group(1)
            number = qs_match.group(2)

            # Replace "10)" -> "10."
            line = qs_pattern.sub(f"{spaces}{number}.", line, count=1)

        else:
            # Replace Op token
            op_match = op_pattern.match(line)

            if op_match:
                spaces = op_match.group(1)
                letter = op_match.group(2)

                replacement = option_map[letter]

                # Replace "A." -> "(a)"
                line = op_pattern.sub(
                    f"{spaces}{replacement}",
                    line,
                    count=1
                )

        output_lines.append(line)

with OUTPUT_FILE.open("w", encoding="utf-8") as f:
    f.writelines(output_lines)

print(f"Processed file written to: {OUTPUT_FILE}")
