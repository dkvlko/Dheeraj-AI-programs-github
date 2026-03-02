#!/bin/bash

for img in *.png; do
    tesseract "$img" "${img%.png}" -l eng
done

