from pathlib import Path
import re
import csv

# File paths
MCQ_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/IdiomsandPhrases_answerspace_seq_f.txt")
CSV_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/Answers-Key-all_csv.txt")
OUTPUT_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/INP_answers_full.txt")

# Regex to detect lines starting with number (e.g., "12." or "12 ")
number_pattern = re.compile(r"^\s*(\d+)[\.\s]")

def load_answers(csv_path):
    """Load CSV answers into a list (1-based indexing)."""
    answers = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                answers.append(row[1].strip())
            else:
                answers.append("")  # fallback if row malformed
    return answers

def process():
    answers = load_answers(CSV_FILE)

    with open(MCQ_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    total_lines = len(lines)

    for i, line in enumerate(lines):
        match = number_pattern.match(line)
        if match:
            N = int(match.group(1))

            # Safety: check bounds
            if 1 <= N <= len(answers):
                ans = answers[N - 1]  # convert to 0-based index
            else:
                ans = ""

            target_index = i + 5  # 5th line below current line

            if target_index < total_lines:
                # Trim existing line and append answer
                lines[target_index] = lines[target_index].strip() + " " + ans + "\n"

    # Write output
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"Done. Output written to: {OUTPUT_FILE}")

if __name__ == "__main__":
    process()
