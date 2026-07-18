#!/usr/bin/env python3

import re
from pathlib import Path

INPUT_FILE = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Krish_EGram10/SPLIT/COMBINED_TEXT/Olymp_10_EGram_full_up3_merged_up1.txt"
)

OUTPUT_FILE = INPUT_FILE.with_name(
    INPUT_FILE.stem + "_answers_replaced.txt"
)

# Regular expressions
question_re = re.compile(r'^\d+\.\s*$|^\d+\.\s+')
option_re = re.compile(r'^([ABCD])\.\s*(.*)$')
answer_re = re.compile(r'^Answer\s*:\s*(.*)$')

lines = INPUT_FILE.read_text(encoding="utf-8").splitlines()

i = 0

while i < len(lines):

    # -----------------------------------------------------
    # Beginning of a question?
    # -----------------------------------------------------
    if question_re.match(lines[i]):

        # Empty arrays
        Opl = []
        Op = []

        # Read next four lines for options
        for j in range(1, 5):

            if i + j >= len(lines):
                break

            m = option_re.match(lines[i + j])

            if m:
                Opl.append(m.group(1).strip())
                Op.append(m.group(2).strip())

        # Continue until next question or Answer line
        k = i + 1

        while k < len(lines):

            # Stop at next question
            if question_re.match(lines[k]):
                break

            am = answer_re.match(lines[k])

            if am:

                ans = am.group(1).strip()

                if ans in Opl:
                    idx = Opl.index(ans)
                    lines[k] = f"Answer : {Op[idx]}"

                break

            k += 1

        i = k

    else:
        i += 1

OUTPUT_FILE.write_text(
    "\n".join(lines) + "\n",
    encoding="utf-8"
)

print("Finished.")
print(f"Output written to:\n{OUTPUT_FILE}")
