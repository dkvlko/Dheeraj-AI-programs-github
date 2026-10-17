#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import os
import sys

def sanitize_gift_text(text):
    replacements = {
        "{": "\\{",
        "}": "\\}",
        "=": "\\=",
        "~": "\\~",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def detect_correct_index(correct_raw, options):
    """
    Detect correct option index from multiple formats:
    1 / 2 / 3 / 4
    A / B / C / D
    Exact answer text
    """

    correct_raw = correct_raw.strip()

    # Case 1 — Number
    if correct_raw.isdigit():
        idx = int(correct_raw) - 1
        if 0 <= idx < len(options):
            return idx

    # Case 2 — Letter
    letter_map = {"A": 0, "B": 1, "C": 2, "D": 3}
    if correct_raw.upper() in letter_map:
        return letter_map[correct_raw.upper()]

    # Case 3 — Match answer text
    for i, opt in enumerate(options):
        if correct_raw.lower() == opt.lower():
            return i

    return None


def tsv_to_gift(input_path):

    if not os.path.exists(input_path):
        print(f"❌ File not found: {input_path}")
        return

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(os.getcwd(), base_name + ".gift")

    questions_converted = 0

    with open(input_path, "r", encoding="utf-8") as tsv_file, \
         open(output_path, "w", encoding="utf-8") as gift_file:

        reader = csv.reader(tsv_file, delimiter="\t")

        for row_num, row in enumerate(reader, start=1):

            print(f"\n🔎 DEBUG Row {row_num} → {row}")

            # Skip empty rows
            if not row or len(row) < 6:
                print(f"⚠️ Skipping row {row_num}: insufficient columns")
                continue

            # Skip header automatically
            if row_num == 1 and "question" in row[0].lower():
                print("ℹ️ Header detected — skipped")
                continue

            question = sanitize_gift_text(row[0].strip())

            options = [
                sanitize_gift_text(row[1].strip()),
                sanitize_gift_text(row[2].strip()),
                sanitize_gift_text(row[3].strip()),
                sanitize_gift_text(row[4].strip()),
            ]


            correct_raw = row[5].strip()

            print(f"   ➤ Correct column raw value: '{correct_raw}'")

            correct_index = detect_correct_index(correct_raw, options)

            if correct_index is None:
                print(f"❌ Row {row_num}: Could not detect correct answer")
                continue

            print(f"   ✅ Detected correct index: {correct_index}")

            # Write GIFT
            gift_file.write(f"::Q{row_num}:: {question} {{\n")

            for i, option in enumerate(options):
                prefix = "=" if i == correct_index else "~"
                gift_file.write(f"{prefix}{option}\n")

            gift_file.write("}\n\n")

            questions_converted += 1

    print("\n==============================")
    print("✅ Conversion completed!")
    print(f"📄 Output file: {output_path}")
    print(f"📝 Questions converted: {questions_converted}")
    print("==============================")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage:")
        print("python convert_tab_gift_moodle.py <path_to_tab_separated_csv>")
    else:
        tsv_to_gift(sys.argv[1])
