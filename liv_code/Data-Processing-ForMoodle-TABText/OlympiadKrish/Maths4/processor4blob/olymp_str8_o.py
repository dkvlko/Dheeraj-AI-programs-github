from pathlib import Path
import re

input_file = Path(
    "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Krish_Maths4/pdfimgs/COMBINED_TEXT/OlympiadMaths_Set1_up1.txt"
)

output_file = Path(
    "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Krish_Maths4/pdfimgs/COMBINED_TEXT/OlympiadMaths_Set1_up2.txt"
)

# Token Op pattern:
# Matches A. B. C. D. at word boundaries
op_pattern = re.compile(r'\b([ABCD])\.')

output_lines = []

with input_file.open("r", encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")

        # Check whether line begins with Op
        if op_pattern.match(line.strip()):

            current = line

            while True:
                matches = list(op_pattern.finditer(current))

                # Need at least 2 Ops in same line
                if len(matches) >= 2:
                    second_match = matches[1]

                    # Split before second Op
                    first_part = current[:second_match.start()].rstrip()
                    second_part = current[second_match.start():].lstrip()

                    output_lines.append(first_part)

                    # Continue processing from second Op onward
                    current = second_part

                else:
                    output_lines.append(current)
                    break

        else:
            output_lines.append(line)

with output_file.open("w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))

print(f"Processed file saved to:\n{output_file}")
