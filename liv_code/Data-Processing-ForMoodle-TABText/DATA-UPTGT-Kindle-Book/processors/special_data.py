import re
import os

input_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/Data-Processing-ForMoodle-TABText/DATA-UPTGT-Kindle-Book/COMBINED_TEXT_KINDLE/special_case.txt"

directory = os.path.dirname(input_file)
output_file = os.path.join(directory, "special_case_processed.txt")

print("Reading file:", input_file)

with open(input_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

print("Total lines read:", len(lines))
print("Processing MCQs...")

mcq = ["", "", "", ""]
output_lines = []

for line in lines:
    stripped = line.strip()

    if re.match(r'^A\)', stripped):
        mcq[0] = stripped
        output_lines.append(line)

    elif re.match(r'^B\)', stripped):
        mcq[1] = stripped
        output_lines.append(line)

    elif re.match(r'^C\)', stripped):
        mcq[2] = stripped
        output_lines.append(line)

    elif re.match(r'^D\)', stripped):
        mcq[3] = stripped
        output_lines.append(line)

    elif stripped.startswith("Answer:"):

        match = re.search(r'Answer:\s*([ABCD])\)', stripped)

        if match:
            option_letter = match.group(1)

            index = ord(option_letter) - ord('A')

            if mcq[index] != "":
                new_line = "Answer: " + mcq[index] + "\n"
                output_lines.append(new_line)
            else:
                output_lines.append(line)

        else:
            output_lines.append(line)

        mcq = ["", "", "", ""]

    else:
        output_lines.append(line)

print("Writing processed file:", output_file)

with open(output_file, "w", encoding="utf-8") as f:
    f.writelines(output_lines)

print("Processing finished successfully.")