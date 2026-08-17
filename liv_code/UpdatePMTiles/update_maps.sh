#!/usr/bin/env bash

set -u

# ============================================================
# Offline India Map Update Script
# ============================================================

# -----------------------------
# Configuration
# -----------------------------

OPENMAPS_ROOT="/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/OpenMapsData"

OSM_DIR="$OPENMAPS_ROOT/osm"
PMTILES_DIR="$OPENMAPS_ROOT/pmtiles"
BACKUP_DIR="$OPENMAPS_ROOT/backups"
LOG_DIR="$OPENMAPS_ROOT/logs"

PLANETILER_DIR="/home/dkvlko/planetiler"
PLANETILER_JAR="$PLANETILER_DIR/planetiler.jar"

# Geofabrik India extract
OSM_URL="https://download.geofabrik.de/asia/india-latest.osm.pbf"

# Your current Martin source
PMTILES="$PMTILES_DIR/india.pmtiles"

# Temporary output during build
NEW_PMTILES="$PMTILES_DIR/india-new.pmtiles"

# -----------------------------
# Create directories
# -----------------------------

mkdir -p "$OSM_DIR"
mkdir -p "$PMTILES_DIR"
mkdir -p "$BACKUP_DIR"
mkdir -p "$LOG_DIR"


# -----------------------------
# Timestamp
# -----------------------------

DATE_TIME=$(date '+%Y-%m-%d_%H-%M-%S')

LOG_FILE="$LOG_DIR/update_$DATE_TIME.log"


# -----------------------------
# Logging
# -----------------------------

exec > >(tee -a "$LOG_FILE") 2>&1


echo
echo "============================================================"
echo "        OFFLINE INDIA MAP UPDATE"
echo "============================================================"
echo
echo "Started: $(date)"
echo


# -----------------------------
# Check required commands
# -----------------------------

for command in wget java; do

    if ! command -v "$command" >/dev/null 2>&1; then

        echo "ERROR: Required command not found: $command"
        exit 1

    fi

done


# -----------------------------
# Check Planetiler
# -----------------------------

if [ ! -f "$PLANETILER_JAR" ]; then

    echo "ERROR:"
    echo "Planetiler JAR not found:"
    echo "$PLANETILER_JAR"

    exit 1

fi


# -----------------------------
# Download latest India PBF
# -----------------------------

echo
echo "Downloading latest India OpenStreetMap PBF..."
echo
echo "Source:"
echo "$OSM_URL"
echo


LATEST_PBF="$OSM_DIR/india-latest.osm.pbf"


rm -f "$LATEST_PBF"


wget \
    --continue \
    --show-progress \
    --output-document="$LATEST_PBF" \
    "$OSM_URL"


if [ $? -ne 0 ]; then

    echo
    echo "ERROR: India PBF download failed."
    exit 1

fi


# -----------------------------
# Check downloaded file
# -----------------------------

if [ ! -s "$LATEST_PBF" ]; then

    echo
    echo "ERROR: Downloaded PBF is empty."
    exit 1

fi


echo
echo "Downloaded PBF:"
ls -lh "$LATEST_PBF"
echo


# -----------------------------
# Determine download date
# -----------------------------

UPDATE_DATE=$(date '+%Y%m%d')

DATED_PBF="$OSM_DIR/india-$UPDATE_DATE.osm.pbf"


# Keep a dated copy.
#
# If one already exists, don't overwrite it.

if [ ! -e "$DATED_PBF" ]; then

    cp "$LATEST_PBF" "$DATED_PBF"

    echo "Saved dated PBF:"
    echo "$DATED_PBF"

else

    echo "Dated PBF already exists:"
    echo "$DATED_PBF"

fi


# -----------------------------
# Remove previous temporary PMTiles
# -----------------------------

rm -f "$NEW_PMTILES"

rm -f "$NEW_PMTILES.layerstats.tsv.gz"


# -----------------------------
# Build new PMTiles
# -----------------------------

echo
echo "============================================================"
echo "Starting Planetiler"
echo "============================================================"
echo

cd "$PLANETILER_DIR" || exit 1


java \
    -Xmx12G \
    -jar "$PLANETILER_JAR" \
    --osm_path="$LATEST_PBF" \
    --output="$NEW_PMTILES"


PLANETILER_STATUS=$?


# -----------------------------
# Check Planetiler result
# -----------------------------

if [ "$PLANETILER_STATUS" -ne 0 ]; then

    echo
    echo "============================================================"
    echo "ERROR: Planetiler FAILED"
    echo "============================================================"
    echo
    echo "Your existing map has NOT been changed."
    echo
    echo "Current PMTiles remains:"
    echo "$PMTILES"
    echo

    rm -f "$NEW_PMTILES"

    exit 1

fi


# -----------------------------
# Verify new PMTiles
# -----------------------------

if [ ! -s "$NEW_PMTILES" ]; then

    echo
    echo "ERROR: Planetiler completed but new PMTiles is missing/empty."
    echo
    echo "Existing map has NOT been changed."

    exit 1

fi


echo
echo "New PMTiles successfully created:"
ls -lh "$NEW_PMTILES"
echo


# -----------------------------
# Backup current PMTiles
# -----------------------------

if [ -f "$PMTILES" ]; then

    BACKUP_FILE="$BACKUP_DIR/india-$DATE_TIME.pmtiles"

    echo "Backing up current PMTiles:"
    echo "$BACKUP_FILE"

    cp "$PMTILES" "$BACKUP_FILE"

    if [ $? -ne 0 ]; then

        echo
        echo "ERROR: Could not create PMTiles backup."
        echo "Existing map has NOT been changed."

        exit 1

    fi

fi


# -----------------------------
# Replace current PMTiles
# -----------------------------

echo
echo "Installing new PMTiles..."
echo


mv "$NEW_PMTILES" "$PMTILES"


if [ $? -ne 0 ]; then

    echo
    echo "ERROR: Could not replace current PMTiles."
    exit 1

fi


echo
echo "============================================================"
echo "MAP UPDATE SUCCESSFUL"
echo "============================================================"
echo
echo "New map:"
echo "$PMTILES"
echo
echo "Size:"
ls -lh "$PMTILES"
echo
echo "Finished: $(date)"
echo
echo "Log:"
echo "$LOG_FILE"
echo


# -----------------------------
# Martin
# -----------------------------

echo
echo "IMPORTANT:"
echo
echo "The PMTiles file has been replaced."
echo
echo "If Martin was started as a systemd service and"
echo "loads the PMTiles at startup, restart Martin now."
echo
echo "For example:"
echo
echo "    sudo systemctl restart martin"
echo
echo "If Martin is running manually in a terminal,"
echo "restart that Martin process instead."
echo


exit 0
