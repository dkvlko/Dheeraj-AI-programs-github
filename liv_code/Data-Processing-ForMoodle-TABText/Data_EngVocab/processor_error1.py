#!/usr/bin/env python3

import os

# File path
file_path = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/Data-Processing-ForMoodle-TABText/Data_EngVocab/12000-Clues-6000-Words.gift"


def process_line(line: str) -> str:
    """
    For every occurrence of '{=' in the line,
    convert the immediate next character to lowercase.
    """

    i = 0
    line_chars = list(line)

    while i < len(line_chars) - 2:
        # Check for token "{="
        if line_chars[i] == '{' and line_chars[i + 1] == '=':
            next_index = i + 2

            # Convert immediate next character to lowercase
            line_chars[next_index] = line_chars[next_index].lower()

            # Move index forward to avoid reprocessing same token
            i = next_index
        else:
            i += 1

    return "".join(line_chars)


def main():
    # Safety check
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    # Read all lines
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Process lines
    processed_lines = [process_line(line) for line in lines]

    # Write back to same file
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(processed_lines)

    print("Processing completed successfully.")


if __name__ == "__main__":
    main()