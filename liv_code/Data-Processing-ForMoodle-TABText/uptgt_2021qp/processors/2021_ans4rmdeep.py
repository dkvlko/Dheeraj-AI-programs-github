
#!/usr/bin/env python3
# Python 3.14

import re

input_file = "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Prka_PQ2021/COMB_TEXT/UPTGT2021-Combined_up2.txt"

output_file = "/home/dkvlko/Dheeraj-Cloud-Drives/DheerajOnHP/BLOBS/Prka_PQ2021/COMB_TEXT/UPTGT2021-Combined_deep.txt"

# Detect lines beginning with a number
number_start_re = re.compile(r'^\s*\d+')

prefix_text = "Can you choose the correct option from the following question?: "


def main():
    output_lines = []

    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            # If line begins with a number
            if number_start_re.match(line):
                line = prefix_text + line

            output_lines.append(line)

    with open(output_file, "w", encoding="utf-8") as f:
        for line in output_lines:
            f.write(line + "\n")

    print("Processing completed.")
    print(f"Output written to:\n{output_file}")


if __name__ == "__main__":
    main()
