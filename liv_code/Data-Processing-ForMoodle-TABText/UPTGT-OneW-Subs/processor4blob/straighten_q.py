from pathlib import Path
import re

INPUT_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/IdiomsandPhrases_Combined.txt")
OUTPUT_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/IdiomsandPhrases_straightq.txt")


def starts_with_number(line: str) -> bool:
    return bool(re.match(r'^\s*\d+\.(?=\s|$)', line))

def has_closing_bracket_in_first_5(line: str) -> bool:
    return ')' in line[:5]


def process_file():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        lines = [line.rstrip() for line in f]

    output_lines = []
    i = 0
    n = len(lines)

    while i < n:
        current_line = lines[i]

        # If line starts with number, begin merging logic
        if starts_with_number(current_line):
            merged_line = current_line
            i += 1

            # Merge subsequent lines based on conditions
            while i < n:
                next_line = lines[i]

                if starts_with_number(next_line):
                    break  # stop merging

                if has_closing_bracket_in_first_5(next_line):
                    break  # stop merging

                # Merge
                merged_line += " " + next_line.strip()
                i += 1

            output_lines.append(merged_line)

        else:
            # If line doesn't start with number, just keep it as is
            output_lines.append(current_line)
            i += 1

    # Write output
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for line in output_lines:
            f.write(line + "\n")


if __name__ == "__main__":
    process_file()
