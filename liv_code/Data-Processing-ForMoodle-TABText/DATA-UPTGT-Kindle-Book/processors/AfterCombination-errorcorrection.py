import re

input_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/Data-Processing-ForMoodle-TABText/DATA-UPTGT-Kindle-Book/COMBINED_TEXT_KINDLE/UPTGT-Eng-Lit_Combined_Text.txt"
output_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/Data-Processing-ForMoodle-TABText/DATA-UPTGT-Kindle-Book/COMBINED_TEXT_KINDLE/UPTGT-Eng-Lit_Combined_Text.txt_2.txt"

patterns = [
    r"left in book",
    r"2500\+ MC",
    r"HINA ENGLISH CLASSES",
    r"Page\s+\d+"
]

with open(input_file, "r", encoding="utf-8") as infile, \
     open(output_file, "w", encoding="utf-8") as outfile:

    for line in infile:
        if not any(re.search(p, line) for p in patterns):
            outfile.write(line)

print("Cleaning completed. Output saved to:", output_file)