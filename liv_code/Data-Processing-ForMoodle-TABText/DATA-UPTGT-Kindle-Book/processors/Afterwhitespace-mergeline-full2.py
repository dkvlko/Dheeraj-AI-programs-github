import re

input_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/Data-Processing-ForMoodle-TABText/DATA-UPTGT-Kindle-Book/COMBINED_TEXT_KINDLE/UPTGT-Eng-Lit_Combined_Text_6.txt"
output_file = input_file.replace(".txt", "_processed.txt")

number_pattern = re.compile(r'\b\d+\.')

with open(input_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

output_lines = []
i = 0

while i < len(lines):
    line = lines[i].rstrip()

    # Check if line contains token like 10. or 45.
    if number_pattern.search(line):

        merged_line = line
        i += 1

        # Merge following lines until ')' appears
        while i < len(lines):
            current = lines[i].strip()

            if ")" in current:
                break

            merged_line += " " + current
            i += 1

        output_lines.append(merged_line)

        # If option line found, write it normally
        if i < len(lines):
            output_lines.append(lines[i].rstrip())
            i += 1

    else:
        output_lines.append(line)
        i += 1

with open(output_file, "w", encoding="utf-8") as f:
    for line in output_lines:
        f.write(line + "\n")

print("Processing complete.")
print("Output file:", output_file)