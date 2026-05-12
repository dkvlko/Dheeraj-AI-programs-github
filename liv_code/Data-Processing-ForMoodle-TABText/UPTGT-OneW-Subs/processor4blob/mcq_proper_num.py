#!/usr/bin/env python3

from pathlib import Path
import re

input_file = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Prka_1WSubs/COMBINED_TEXT/OWSubs_Comb_up2.txt"
)

output_file = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Prka_1WSubs/COMBINED_TEXT/OWSubs_Comb_up3.txt"
)

seqn = 0

pattern = re.compile(r'^(\s*)\d+\.')

with input_file.open("r", encoding="utf-8") as fin, \
     output_file.open("w", encoding="utf-8") as fout:

    for line in fin:

        if pattern.match(line):
            seqn += 1

            # Replace only the leading number token
            line = pattern.sub(rf'\g<1>{seqn}.', line, count=1)

        fout.write(line)

print(f"Done. Output written to:\n{output_file}")
