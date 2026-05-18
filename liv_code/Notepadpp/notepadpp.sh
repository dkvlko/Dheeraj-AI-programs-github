#!/bin/bash

folder="/home/dkvlko/tmp"

LOCKFILE="/tmp/open_notes.lock"

exec 200>"$LOCKFILE"

flock -n 200 || {
    echo "Already running."
    exit 1
}

vim --cmd "cd $folder" -p "$folder"/*.txt
