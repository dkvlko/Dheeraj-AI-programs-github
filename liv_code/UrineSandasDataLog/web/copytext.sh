#!/bin/bash

INPUT_TEXT=$(cat)

# Use xclip (install if needed: sudo apt install xclip)
echo -n "$INPUT_TEXT" | xclip -selection clipboard
