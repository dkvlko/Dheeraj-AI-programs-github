from pathlib import Path
import re

# Input and Output paths
INPUT_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/IdiomsandPhrases_Combined.txt")
OUTPUT_FILE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Priyanka-Idioms-Phrases/COMBINED_TEXT/IdiomsandPhrases_qcount.txt")

# Regex to match "number." at the beginning of a line
pattern = re.compile(r'^\s*(\d+)\.')

results = []
seq_counter = 1

# Read file
with INPUT_FILE.open("r", encoding="utf-8") as f:
    for line in f:
        match = pattern.search(line)
        if match:
            number_str = match.group(1)        # e.g. "10"
            original_format = match.group(0).strip()  # e.g. "10."
            number_int = int(number_str)

            results.append((seq_counter, original_format, number_int))
            seq_counter += 1

# Write output
with OUTPUT_FILE.open("w", encoding="utf-8") as f:
    for seq, original, num in results:
        f.write(f"{seq}\t{original}\t{num}\n")

print(f"Done. Found {len(results)} numbered lines.")
