#!/usr/bin/env python3

import re
from pathlib import Path

QUESTION_FILE = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Krish_EGram10/SPLIT/COMBINED_TEXT/Olymp_10_EGram_full_up3.txt"
)

ANSWER_FILE = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Krish_EGram10/SPLIT/COMBINED_TEXT/Olymp_10_EGram_full_ans_up1.txt"
)

OUTPUT_FILE = QUESTION_FILE.with_name(
    QUESTION_FILE.stem + "_merged.txt"
)

token_re = re.compile(r'^(\d+)\.\s*(.*)$')

# ---------------------------------------------------------
# Read both files
# ---------------------------------------------------------
question_lines = QUESTION_FILE.read_text(
    encoding="utf-8"
).splitlines()

answer_lines = ANSWER_FILE.read_text(
    encoding="utf-8"
).splitlines()

# ---------------------------------------------------------
# Output list
# ---------------------------------------------------------
output = []

answer_index = 0

i = 0
while i < len(question_lines):

    line = question_lines[i]
    output.append(line)

    m = token_re.match(line)

    if m:
        token = m.group(1)

        # Search only below previous match
        while answer_index < len(answer_lines):

            am = token_re.match(answer_lines[answer_index])

            if am:
                answer_token = am.group(1)

                if answer_token == token:

                    answer_text = am.group(2)

                    # Copy next 4 original lines
                    for k in range(1, 5):
                        if i + k < len(question_lines):
                            output.append(question_lines[i + k])
                            #print("Question line copy :",question_lines[i+k])
                    #print("Printed")
                    # Insert answer
                    output.append(answer_text)

                    # Skip those 4 lines already copied
                    i += 4

                    answer_index += 1
                    break

            answer_index += 1

    i += 1

OUTPUT_FILE.write_text(
    "\n".join(output) + "\n",
    encoding="utf-8"
)

print("Finished.")
print("Output written to:")
print(OUTPUT_FILE)
