import re

input_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/INP_answers_intext_full.txt"
output_file = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/autotag_AIqinp_queries.txt"

def extract_question(line):
    # Match lines like "12. some text..."
    match = re.match(r'^\s*(\d+\.)\s*(.*)', line)
    if match:
        return match.group(2).strip()
    return None

def extract_answer(line):
    # Extract text after "Answer :"
    match = re.search(r'Answer\s*:\s*(.*)', line, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

with open(input_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

queries = []
i = 0
n = len(lines)

while i < n:
    line = lines[i].strip()

    q1 = extract_question(line)

    if q1:
        # Try to get 5th line below
        answer_line_index = i + 5

        a1 = None

        if answer_line_index < n:
            a1 = extract_answer(lines[answer_line_index])

        # Fallback: search forward if not found exactly at +5
        if not a1:
            for j in range(i + 1, min(i + 10, n)):
                a1 = extract_answer(lines[j])
                if a1:
                    break

        if a1:
            query = f'Can you put HTML tags texts <u> </u> around 3-4 words which stand for "{a1}" in the sentence "{q1}"?'
            queries.append(query)

        # Move forward to next question (skip until next numbered line)
        i += 1
        while i < n and not re.match(r'^\s*\d+\.', lines[i]):
            i += 1
    else:
        i += 1

# Write output
with open(output_file, "w", encoding="utf-8") as f:
    for q in queries:
        f.write(q + "\n")

print(f"Done. {len(queries)} queries written to output file.")
