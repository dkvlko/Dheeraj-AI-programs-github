#!/bin/bash
set -e

BASE="/home/dkvlko/live_code/TVAndroidRemote"
VENV="/home/dkvlko/python314_projects/venv_3.14"
SYSTEMD="/etc/systemd/system"

echo "Installing Android TV remote service..."

#sudo mkdir -p "$BASE"
#sudo cp tvandroidremote_daemon.py "$BASE/"
#sudo cp tvremote.py "$BASE/"
#sudo cp tvremote_api.py "$BASE/"
sudo cp tvandroidremote.service "$SYSTEMD/"

sudo chown dkvlko:dkvlko \
    "$BASE/tvandroidremote_daemon.py" \
    "$BASE/tvremote.py" \
    "$BASE/tvremote_api.py"

sudo chmod 755 \
    "$BASE/tvandroidremote_daemon.py" \
    "$BASE/tvremote.py" \
    "$BASE/tvremote_api.py"

sudo systemctl daemon-reload
sudo systemctl enable --now tvandroidremote.service

echo
echo "Service status:"
sudo systemctl --no-pager --full status tvandroidremote.service
