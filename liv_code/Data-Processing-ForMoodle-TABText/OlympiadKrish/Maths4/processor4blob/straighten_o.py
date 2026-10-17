from pathlib import Path
import re

INPUT_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/IdiomsandPhrases_straightq.txt")
OUTPUT_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/IdiomsandPhrases_final.txt")


def starts_with_number(line: str) -> bool:
    return bool(re.match(r'^\s*\d+\.(?=\s|$)', line))


def is_A(line: str) -> bool:
    """
    A line is A-type if it contains '(' and ')' with <=3 chars between them
    """
    matches = re.findall(r'\((.*?)\)', line)
    for m in matches:
        if len(m) <= 3:
            return True
    return False


def process_file():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        lines = [line.rstrip() for line in f]

    output_lines = []
    i = 0
    n = len(lines)

    while i < n:
        current_line = lines[i]

        if is_A(current_line):
            merged_line = current_line
            i += 1

            while i < n:
                next_line = lines[i]

                if is_A(next_line):
                    break

                if starts_with_number(next_line):
                    break

                merged_line += " " + next_line.strip()
                i += 1

            output_lines.append(merged_line)

        else:
            output_lines.append(current_line)
            i += 1

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for line in output_lines:
            f.write(line + "\n")


if __name__ == "__main__":
    process_file()
