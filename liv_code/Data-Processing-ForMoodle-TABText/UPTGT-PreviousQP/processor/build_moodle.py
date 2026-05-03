#!/usr/bin/env python3
"""
Create Moodle Question Bank
Python 3.14 compatible
(Directory structure adapted as requested)
"""

from pathlib import Path
import re
import sys


def main():

    # --------------------------------------------------
    # Initialize directories
    # --------------------------------------------------

    SCRIPT_DIR = Path(__file__).resolve().parent
    INPUT_DIR = SCRIPT_DIR.parent

    TEXT_DIR = INPUT_DIR / "DATA"

    INPUT_FILE = TEXT_DIR / "UP_TGT_Questions_with_answers.txt"
    OUTPUT_FILE = TEXT_DIR / "UP_TGT_Questions_with_answers_moodle.txt"

    if not INPUT_FILE.exists():
        print("Input file not found.")
        sys.exit(1)

    print(f"SCRIPT_DIR : {SCRIPT_DIR}")
    print(f"INPUT_FILE : {INPUT_FILE}")
    print(f"OUTPUT_FILE: {OUTPUT_FILE}")
    print("--------------------------------------------------")

    # ---------- Initialisation ----------
    SNo = 0
    Op = 0

    question = []
    options = []
    ans = []

    # ---------- Read File ----------
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    current_q = -1   # no question yet
    i = 0
    while i < len(lines):

        line = lines[i]

        # -------- Detect Question (number.) ----------
        if re.match(r'^\d+\.', line):
            qtext = re.sub(r'^\d+\.\s*', '', line)
            question.append(qtext)
            options.append([])
            ans.append("")
            current_q += 1
            i += 1
            continue
        # Ignore anything before first question
        if current_q < 0:
            i += 1
            continue
        # -------- Detect Answer ----------
        if "Answer" in line:
            #match = re.search(r'\)(.*)', line)
            match = re.search(r':\s*(.*)', line)
            if match:
                ans[current_q] = match.group(1).strip()

            i += 1
            continue

        # -------- Otherwise treat as Option ----------
        match = re.search(r'\)(.*)', line)
        if match:
            option_text = match.group(1).strip()
            options[current_q].append(option_text)

        i += 1

    # ---------- Construct Moodle Questions ----------
    QuestionBank = []

    for idx in range(len(question)):

        QuestionMoodle = "::"
        QuestionMoodle += str(idx + 1)
        QuestionMoodle += "::"
        QuestionMoodle += question[idx]
        QuestionMoodle += " {="

        QuestionMoodle += ans[idx]
        #result=" ".join(QuestionMoodle)
        #print("Question : ",result)
        #print("Question :",question[idx])
        #print("Answer :",ans[idx])

        for opt in options[idx]:
            if opt != ans[idx]:
                QuestionMoodle += " ~" + opt

        QuestionMoodle += "}"

        QuestionBank.append(QuestionMoodle)

    # ---------- Save Output ----------
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        for q in QuestionBank:
            f.write(q + "\n\n")

    print("Done.")
    print("Output saved to:")
    print(OUTPUT_FILE)

    sys.exit(0)


if __name__ == "__main__":
    main()
