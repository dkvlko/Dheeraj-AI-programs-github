import re

INPUT_FILE = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Prka_1WSubs/COMBINED_TEXT/MCQ_Complete.txt"
OUTPUT_FILE = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Prka_1WSubs/COMBINED_TEXT/MCQ_Complete_up1.txt"

def is_question_line(line):
    return re.match(r'^\s*\d+\.', line)

def parse_option(line):
    """
    Matches lines like:
    (A) option text
    (b) option text
    """
    match = re.match(r'^\s*\(([A-Za-z]{1,2})\)\s*(.*)', line)
    if match:
        key = match.group(1).strip().lower()   # case-insensitive key
        value = match.group(2).strip()         # case-sensitive text
        return key, value
    return None, None

def extract_answer(line):
    match = re.search(r'Answer\s*:\s*(.*)', line, re.IGNORECASE)
    if match:
        return match.group(1).strip().lower()
    return None

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    output_lines = []

    while i < len(lines):
        line = lines[i]

        if is_question_line(line):
            output_lines.append(line)
            i += 1

            options = {}

            # Read next 4 option lines
            for _ in range(4):
                if i >= len(lines):
                    break

                opt_line = lines[i]
                key, value = parse_option(opt_line)

                if key:
                    options[key] = value

                output_lines.append(opt_line)
                i += 1

            # 5th line → Answer
            if i < len(lines):
                ans_line = lines[i]
                ans_key = extract_answer(ans_line)

                if ans_key and ans_key in options:
                    new_line = f"Answer : {options[ans_key]}\n"
                else:
                    new_line = ans_line  # fallback if something is off

                output_lines.append(new_line)
                i += 1

        else:
            # Normal line
            output_lines.append(line)
            i += 1

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(output_lines)

    print("Done. Output written to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
