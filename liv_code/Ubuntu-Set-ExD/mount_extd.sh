#!/bin/bash

##############################################################################
# Mount WD External Drives by UUID
##############################################################################

set -u

##############################################################################
# Configuration
##############################################################################

ELEMENTS_UUID="18B6B61CB6B5F9F8"
PASSPORT_UUID="1006E76C06E75170"

ELEMENTS_MOUNT="/media/Elements"
PASSPORT_MOUNT="/media/My Passport"

##############################################################################

echo "============================================================"
echo " WD External Drive Mount Utility"
echo "============================================================"
echo

##############################################################################
# Create mount points
##############################################################################

sudo mkdir -p "$ELEMENTS_MOUNT"
sudo mkdir -p "$PASSPORT_MOUNT"

##############################################################################
# Unmount existing mounts
##############################################################################

echo "Unmounting drives (if mounted)..."

if mountpoint -q "$ELEMENTS_MOUNT"; then
    echo "  Unmounting Elements..."
    sudo umount "$ELEMENTS_MOUNT"
fi

if mountpoint -q "$PASSPORT_MOUNT"; then
    echo "  Unmounting My Passport..."
    sudo umount "$PASSPORT_MOUNT"
fi

echo

##############################################################################
# Mount Elements
##############################################################################

echo "Searching for Elements drive..."

ELEMENTS_DEV=$(blkid -U "$ELEMENTS_UUID" 2>/dev/null)

if [[ -n "$ELEMENTS_DEV" ]]; then
    echo "Found: $ELEMENTS_DEV"

    if sudo mount UUID="$ELEMENTS_UUID" "$ELEMENTS_MOUNT"; then
        echo "✓ Elements mounted successfully."
    else
        echo "✗ Failed to mount Elements."
    fi
else
    echo "✗ Elements drive not connected."
fi

echo

##############################################################################
# Mount My Passport
##############################################################################

echo "Searching for My Passport drive..."

PASSPORT_DEV=$(blkid -U "$PASSPORT_UUID" 2>/dev/null)

if [[ -n "$PASSPORT_DEV" ]]; then
    echo "Found: $PASSPORT_DEV"

    if sudo mount UUID="$PASSPORT_UUID" "$PASSPORT_MOUNT"; then
        echo "✓ My Passport mounted successfully."
    else
        echo "✗ Failed to mount My Passport."
    fi
else
    echo "✗ My Passport drive not connected."
fi

echo

##############################################################################
# Final Status
##############################################################################

echo "============================================================"
echo "Mounted Drives"
echo "============================================================"

findmnt "$ELEMENTS_MOUNT"
findmnt "$PASSPORT_MOUNT"

echo
echo "Done."
