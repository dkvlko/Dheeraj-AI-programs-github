#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
from pathlib import Path

# -------- FILE NAMES --------
input_file = "english_test_1.csv"
output_file = "english_test_1_out.csv"
# ----------------------------


def init_files():
    """
    Recyclable file initialization.
    Opens input for reading and output for writing
    in TAB-delimited mode.
    Returns file handles and CSV reader/writer.
    """

    script_dir = Path(__file__).parent.resolve()

    in_path = script_dir / input_file
    out_path = script_dir / output_file

    infile = open(in_path, mode="r", encoding="utf-8", newline="")
    outfile = open(out_path, mode="w", encoding="utf-8", newline="")

    reader = csv.reader(infile, delimiter="\t")
    writer = csv.writer(outfile, delimiter="\t")

    return infile, outfile, reader, writer


def main():
    infile, outfile, reader, writer = init_files()

    print("\n--- Printing Columns from Input File ---\n")

    for row_num, row in enumerate(reader, start=1):

        # Print each column value
        print(f"Row {row_num}:")
        for col_num, col_value in enumerate(row, start=1):
            print(f"  Column {col_num} = {col_value}")

        print("-" * 40)

        # Copy row to output file
        writer.writerow(row)

    infile.close()
    outfile.close()

    print("\nData copied successfully to:", output_file)


if __name__ == "__main__":
    main()
