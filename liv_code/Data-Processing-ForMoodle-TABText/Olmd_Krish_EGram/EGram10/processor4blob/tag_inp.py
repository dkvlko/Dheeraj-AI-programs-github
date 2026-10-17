from pathlib import Path

# File paths
m_text_path = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/INP_answers_intext_full_formoodle.txt")
tag_path = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/tagged_inp4python.txt")
output_path = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/INP_tagged_full_formoodle.txt")

# Read files
with m_text_path.open("r", encoding="utf-8") as f:
    m_lines = f.readlines()

with tag_path.open("r", encoding="utf-8") as f:
    tag_lines = [line.strip() for line in f.readlines()]

# Safety check
if len(tag_lines) < len(m_lines):
    raise ValueError("tag_4python has fewer lines than M_text. Cannot map line-by-line.")

processed_lines = []

for i, line in enumerate(m_lines):
    tag_text = tag_lines[i]

    # Find first and second occurrence of "::"
    first = line.find("::")
    if first == -1:
        processed_lines.append(line)
        continue

    second = line.find("::", first + 2)
    if second == -1:
        processed_lines.append(line)
        continue

    # Find first "{" after second "::"
    brace = line.find("{", second + 2)
    if brace == -1:
        processed_lines.append(line)
        continue

    # Construct new line
    new_line = (
        line[:second + 2] +    # up to and including second "::"
        tag_text +             # replacement text
        line[brace:]           # from "{"
    )

    processed_lines.append(new_line)

# Write output
with output_path.open("w", encoding="utf-8") as f:
    f.writelines(processed_lines)

print("Processing complete. Output saved to:", output_path)
