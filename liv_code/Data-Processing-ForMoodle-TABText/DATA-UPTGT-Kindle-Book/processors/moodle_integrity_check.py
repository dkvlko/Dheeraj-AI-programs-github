import re

input_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/Data-Processing-ForMoodle-TABText/DATA-UPTGT-Kindle-Book/COMBINED_TEXT_KINDLE/UPTGT-Eng-Lit_Combined_Text_final.txt"
output_file = input_file.replace(".txt", "_check.txt")

with open(input_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

output_lines = []

for line in lines:

    line_stripped = line.strip()

    # Check if line is a Moodle MCQ
    if re.match(r'^::\d+::', line_stripped):

        # extract text inside { }
        match = re.search(r'\{(.*)\}', line_stripped)

        if match:
            options_text = match.group(1)

            # count options (= or ~)
            options = re.findall(r'[=~]', options_text)

            if len(options) != 4:
                output_lines.append("#FIXIT\n")

        else:
            # malformed question without {}
            output_lines.append("#FIXIT\n")

    output_lines.append(line)

with open(output_file, "w", encoding="utf-8") as f:
    f.writelines(output_lines)

print("Integrity check completed.")
print("Output written to:", output_file)