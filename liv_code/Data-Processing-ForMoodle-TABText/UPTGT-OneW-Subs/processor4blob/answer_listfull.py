#!/usr/bin/env python3
# Python 3.14 compatible

from pathlib import Path

# Input and output files
T1_PATH = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Prka_1WSubs/COMBINED_TEXT/ans_key1.txt"
)

T2_PATH = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Prka_1WSubs/COMBINED_TEXT/ans_key_full.txt"
)


def process_file():
    output_lines = []
    sno = 1

    # Read all lines
    with T1_PATH.open("r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    # Process 2 lines at a time
    for i in range(0, len(lines), 2):

        # Ensure second line exists
        if i + 1 >= len(lines):
            print(f"Warning: unmatched line at end of file near line {i + 1}")
            break

        # First line -> QNo array
        QNo = [x.strip() for x in lines[i].split(",")]

        # Second line -> Ano array
        Ano = [x.strip() for x in lines[i + 1].split(",")]

        # Use smaller length if mismatch occurs
        pair_count = min(len(QNo), len(Ano))

        if len(QNo) != len(Ano):
            print(
                f"Warning: column mismatch at line pair "
                f"{i + 1}-{i + 2} "
                f"(QNo={len(QNo)}, Ano={len(Ano)})"
            )

        # Create T2 rows in memory
        for idx in range(pair_count):
            row = f"{sno},{QNo[idx]},{Ano[idx]}"
            output_lines.append(row)
            sno += 1

    # Save T2 file
    with T2_PATH.open("w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    print(f"Done.")
    print(f"Output written to: {T2_PATH}")
    print(f"Total rows created: {len(output_lines)}")


if __name__ == "__main__":
    process_file()
