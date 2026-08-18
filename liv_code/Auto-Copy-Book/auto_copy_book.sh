#!/bin/bash

COUNT=340

for ((i=1;i<=COUNT;i++))
do
    echo "Iteration $i / $COUNT"
    sleep 2

    # Left mouse click
    xdotool click 1

    sleep 2

    # Trigger your PrtSc-mapped script
    xdotool key Print

    sleep 2
done
