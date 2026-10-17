from pathlib import Path

input_file = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/Answers-Key4.txt")
output_file = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/Answers-Key4_csv.txt")

with input_file.open("r", encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()]

merged_lines = []

i = 0
while i < len(lines):
    L1 = lines[i] + ","  # append comma
    if i + 1 < len(lines):
        L2 = lines[i + 1]
        merged_lines.append(L1 + L2)
        i += 2  # skip L2 (deleted logically)
    else:
        # handle odd number of lines (last line without pair)
        merged_lines.append(L1.rstrip(","))
        i += 1

with output_file.open("w", encoding="utf-8") as f:
    for line in merged_lines:
        f.write(line + "\n")

print("Done. Output saved to:", output_file)
