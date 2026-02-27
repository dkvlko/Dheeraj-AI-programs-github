#!/usr/bin/env python3
"""
Convert Moodle GIFT MCQ file → Anki importable TSV flashcards

FRONT = Question
BACK  = Correct Answer
"""

from pathlib import Path
import re

# =========================
# CONFIGURATION
# =========================

SCRIPT_DIR = Path(__file__).resolve().parent

# INPUT_DIR = one level up
INPUT_DIR = SCRIPT_DIR.parent / "COMBINED_TEXT_KINDLE"
INPUT_FILE = INPUT_DIR  / "UPTGT-Eng-Lit_Combined_Text_final.txt"
OUTPUT_FILE = INPUT_DIR / "UPTGT-Eng-Lit-anki_flashcards.csv"

# =========================
# FUNCTIONS
# =========================

def parse_gift(content: str):
    """
    Parse Moodle GIFT MCQs.
    Returns list of (question, answer).
    """

    cards = []

    # Match blocks like:
    # ::1::Question text {answers}
    pattern = re.compile(
        r"::.*?::(.*?)\{(.*?)\}",
        re.DOTALL
    )

    matches = pattern.findall(content)

    for question, answers_block in matches:

        # Clean question
        question = " ".join(question.split())

        # Find correct answer (=)
        correct_match = re.search(r"=([^~}]*)", answers_block)

        if correct_match:
            answer = correct_match.group(1).strip()

            # normalize whitespace
            answer = " ".join(answer.split())

            cards.append((question, answer))

    return cards


def write_anki_tsv(cards, output_path):
    """Write cards into Anki TSV format"""

    with open(output_path, "w", encoding="utf-8") as f:
        for front, back in cards:
            # TAB separated
            f.write(f"{front}\t{back}\n")


# =========================
# MAIN
# =========================

def main():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    content = INPUT_FILE.read_text(encoding="utf-8")

    cards = parse_gift(content)

    if not cards:
        print("No cards found.")
        return

    write_anki_tsv(cards, OUTPUT_FILE)

    print(f"✅ Created {len(cards)} Anki cards")
    print(f"Output file: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()