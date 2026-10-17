import os
import re
import csv

# Target directory
folder_path = "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/GATE-2026-GA"

# Regex pattern: strictly match GATEMCQ_<number>.png
pattern = re.compile(r"^GATEMCQ_(\d+)\.png$")

# Output CSV file
output_csv = os.path.join(folder_path, "output.csv")

# Collect valid filenames
valid_files = []

for file_name in os.listdir(folder_path):
    match = pattern.match(file_name)
    if match:
        valid_files.append(file_name)

# Sort files numerically based on extracted number
valid_files.sort(key=lambda x: int(pattern.match(x).group(1)))

# Write CSV
with open(output_csv, mode='w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    
    # Header
    writer.writerow(["filename", "answer"])
    
    # Rows
    for file_name in valid_files:
        writer.writerow([file_name, "A"])

print(f"CSV file created at: {output_csv}")