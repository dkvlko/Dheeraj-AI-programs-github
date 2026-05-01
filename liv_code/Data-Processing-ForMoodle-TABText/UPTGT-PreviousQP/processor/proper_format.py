from pathlib import Path
import csv

# --------------------------------------------------
# Initialize directories
# --------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_DIR = SCRIPT_DIR.parent

TEXT_DIR = INPUT_DIR / "DATA"

INPUT_FILE = TEXT_DIR / "UP_TGT_Questions_with_answers.csv"
OUTPUT_FILE = TEXT_DIR / "UP_TGT_Questions_with_answers.txt"


def process_csv():
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8", newline="") as infile, \
         open(OUTPUT_FILE, "w", encoding="utf-8") as outfile:

        reader = csv.reader(infile, delimiter="\t")

        for row_num, row in enumerate(reader, start=1):
            # Skip empty or malformed rows
            if len(row) < 7:
                print(f"Skipping row {row_num}: not enough columns")
                continue

            serial = row[0].strip()
            question = row[1].strip()
            opt_a = row[2].strip()
            opt_b = row[3].strip()
            opt_c = row[4].strip()
            opt_d = row[5].strip()
            answer = row[6].strip()

            # Build formatted text
            formatted_text = (
                f"{serial}. {question}\n"
                f"a) {opt_a}\n"
                f"b) {opt_b}\n"
                f"c) {opt_c}\n"
                f"d) {opt_d}\n"
                f"Answer: {answer}\n"
            )

            outfile.write(formatted_text)

    print(f"Processing complete. Output written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    process_csv()
