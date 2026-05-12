from pathlib import Path
import re

INPUT_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/IdiomsandPhrases_final.txt")
OUTPUT_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/IdiomsandPhrases_answerspace.txt")


def starts_with_number(line: str) -> bool:
    return bool(re.match(r'^\s*\d+\.(?=\s|$)', line))


def starts_with_answer(line: str) -> bool:
    return line.strip().startswith("Answer :")


def process_file():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        lines = [line.rstrip() for line in f]

    i = 0
    n = len(lines)

    while i < n:
        if starts_with_number(lines[i]):
            target_index = i + 5

            # Check if 5th line exists
            if target_index < len(lines):
                if not starts_with_answer(lines[target_index]):
                    lines.insert(target_index, "Answer :")
                    n += 1  # update length after insertion

            # Move to next line after current
            i += 1
        else:
            i += 1

    # Write output
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


if __name__ == "__main__":
    process_file()
