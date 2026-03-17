import re

input_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/Data-Processing-ForMoodle-TABText/DATA-UPTGT-Kindle-Book/COMBINED_TEXT_KINDLE/UPTGT-Eng-Lit_Combined_Text_9_formoodle.txt"
output_file = input_file.replace(".txt", "_checked.txt")

with open(input_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

output = []

i = 0
while i < len(lines):

    line = lines[i]
    qcheck = 0
    acheck = 0

    # check for question number like 10. 45. etc
    if re.search(r'^\s*\d+\.', line):
        qcheck = 1
        output.append(line)
        i += 1

        # count consecutive lines containing ")"
        start_i = i

        while i < len(lines) and ")" in lines[i]:
            acheck += 1
            output.append(lines[i])
            i += 1

        # integrity check
        if acheck != 5 or qcheck == 0:
            output.insert(len(output) - acheck, "#FIXIT\n")

        # do NOT skip the current line; it will be reprocessed
        continue

    else:
        output.append(line)
        i += 1


with open(output_file, "w", encoding="utf-8") as f:
    f.writelines(output)

print("Finished. Output written to:", output_file)