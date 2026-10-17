input_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/Data-Processing-ForMoodle-TABText/DATA-UPTGT-Kindle-Book/COMBINED_TEXT_KINDLE/UPTGT-Eng-Lit_Combined_Text_2.txt"
output_file = input_file + ".processed"

with open(input_file, "r", encoding="utf-8") as fin, open(output_file, "w", encoding="utf-8") as fout:
    for line in fin:
        # Remove lines that contain only whitespace
        if line.strip() == "":
            continue

        # Replace leading "." with "10."
        if line.startswith("."):
            line = "10." + line[1:]

        fout.write(line)

print("Processing complete. Output written to:", output_file)