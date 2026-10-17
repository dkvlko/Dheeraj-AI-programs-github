from pathlib import Path
import re

INPUT_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/IdiomsandPhrases_answerspace_seq.txt")
OUTPUT_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/IdiomsandPhrases_answerspace_seq_f.txt")


def extract_number(line: str):
    """
    Returns integer number if line starts with number., else None
    """
    match = re.match(r'^(\s*)(\d+)\.(?=\s|$)', line)
    if match:
        spaces, num = match.groups()
        return spaces, int(num)
    return None, None


def replace_number(line: str, new_number: int):
    match = re.match(r'^(\s*)\d+\.(?=\s|$)', line)
    if match:
        spaces = match.group(1)
        rest = line[match.end():]
        return f"{spaces}{new_number}.{rest}"
    return line

def process_file():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    N1 = None  # previous number

    for i in range(len(lines)):
        line = lines[i]
        spaces, num = extract_number(line)

        if num is not None:
            if N1 is None:
                # first numbered line
                N1 = num
            else:
                expected = N1 + 1
                if num != expected:
                    # fix numbering
                    lines[i] = replace_number(line, expected)
                    num = expected

                N1 = num  # update sequence

    # write output
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        f.writelines(lines)


if __name__ == "__main__":
    process_file()
