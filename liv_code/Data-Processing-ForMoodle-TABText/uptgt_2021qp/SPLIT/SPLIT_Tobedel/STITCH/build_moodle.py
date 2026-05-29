#!/usr/bin/env python3

import os
import re

INPUT_FILE = "/home/dkvlko/Pictures/UPTGT/SPLIT/STITCH/UPTGT_Combined_QA_tight_fixed_formoodle.txt"

# ---------- Initialisation ----------
SNo = 0
Op = 0

question = []
options = []
ans = []

# ---------- Read File ----------
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()]

i = 0
while i < len(lines):

    line = lines[i]

    # -------- Detect Question (number.) ----------
    if re.match(r'^\d+\.', line):
        qtext = re.sub(r'^\d+\.\s*', '', line)
        question.append(qtext)
        options.append([])
        ans.append("")
        Op = 0
        i += 1
        continue

    # -------- Detect Answer ----------
    if "Answer" in line:
        match = re.search(r'\)(.*)', line)
        if match:
            answer_text = match.group(1).strip()
            ans[SNo] = answer_text
        SNo += 1
        Op = 0
        i += 1
        continue

    # -------- Otherwise treat as Option ----------
    match = re.search(r'\)(.*)', line)
    if match:
        option_text = match.group(1).strip()
        options[SNo].append(option_text)
        Op += 1

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

    for opt in options[idx]:
        if opt != ans[idx]:
            QuestionMoodle += " ~" + opt

    QuestionMoodle += "}"

    QuestionBank.append(QuestionMoodle)

# ---------- Save Output ----------
dir_path = os.path.dirname(INPUT_FILE)
base_name = os.path.basename(INPUT_FILE).replace(".txt", "")
output_file = os.path.join(dir_path, base_name + "_final.txt")

with open(output_file, "w", encoding="utf-8") as f:
    for q in QuestionBank:
        f.write(q + "\n\n")

print("Done.")
print("Output saved to:")
print(output_file)
