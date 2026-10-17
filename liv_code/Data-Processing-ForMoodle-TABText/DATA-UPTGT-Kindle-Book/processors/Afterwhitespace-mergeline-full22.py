import re

input_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/Data-Processing-ForMoodle-TABText/DATA-UPTGT-Kindle-Book/COMBINED_TEXT_KINDLE/UPTGT-Eng-Lit_Combined_Text_8.txt"
output_file = input_file.replace(".txt", "_processed.txt")

number_pattern = re.compile(r'\b\d+\.')   # matches 10. 45. 67.

with open(input_file, "r", encoding="utf-8") as f:
    lines = [l.rstrip() for l in f]

output_lines = []
i = 0

while i < len(lines):

    line = lines[i]

    if ")" in line:
        merged_line = line
        i += 1

        while i < len(lines):

            current = lines[i]

            if ")" in current or number_pattern.search(current):
                break

            merged_line += " " + current.strip()
            i += 1

        output_lines.append(merged_line)

    else:
        output_lines.append(line)
        i += 1

with open(output_file, "w", encoding="utf-8") as f:
    for l in output_lines:
        f.write(l + "\n")

print("Processing complete.")
print("Output written to:", output_file)