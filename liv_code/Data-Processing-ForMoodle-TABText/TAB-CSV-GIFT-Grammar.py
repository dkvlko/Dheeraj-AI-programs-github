import csv
from collections import defaultdict

# -------- CONFIG --------
input_file = "English Grammar In Use Exercises_For_Moodle.csv"   # <-- your TAB delimited source file
output_prefix = "english_" # prefix for output files
output_ext = ".csv"
# ------------------------



grouped_data = defaultdict(list)

# Read TAB delimited file
with open(input_file, "r", encoding="utf-8") as f:
    reader = csv.reader(f, delimiter="\t")

    for row in reader:
        if len(row) < 2:
            continue  # skip incomplete rows

        question_type = row[1].strip()
        grouped_data[question_type].append(row)

# Write split files
file_counter = 1

for qtype, rows in grouped_data.items():
    file_name = f"{output_prefix}{file_counter}{output_ext}"

    with open(file_name, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerows(rows)

    print(f"Created: {file_name} → {qtype}")

    file_counter += 1

print("\nSplitting complete.")
