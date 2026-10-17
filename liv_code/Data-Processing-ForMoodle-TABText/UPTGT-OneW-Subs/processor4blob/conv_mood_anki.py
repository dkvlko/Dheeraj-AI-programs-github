import re

input_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Prka_1WSubs/COMBINED_TEXT/MCQ_Complete_moodle.txt"
output_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Prka_1WSubs/COMBINED_TEXT/MCQ_Complete_anki.txt"

with open(input_file, "r", encoding="utf-8") as fin, \
     open(output_file, "w", encoding="utf-8") as fout:

    for line in fin:
        line = line.strip()

        # --- Extract Q1 (between 2nd :: and {) ---
        parts = line.split("::")
        if len(parts) >= 3:
            after_second_colon = parts[2]
            q_match = re.search(r'(.*?)\{', after_second_colon)
            Q1 = q_match.group(1).strip() if q_match else ""
        else:
            Q1 = ""

        # --- Extract A1 (between {= and ~) ---
        a_match = re.search(r'\{=(.*?)~', line)
        A1 = a_match.group(1).strip() if a_match else ""

        # --- Write if both exist ---
        if Q1 and A1:
            fout.write(f"{Q1}\t{A1}\n")
