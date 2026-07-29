#!/bin/bash

##############################################################################
# Mount WD External Drives
##############################################################################

MOUNT1="/media/dkvlko/Elements"
MOUNT2="/media/dkvlko/My Passport"

DEV1="/dev/sdb1"
DEV2="/dev/sdc1"

echo "------------------------------------------------------------"
echo "Unmounting external drives (if mounted)..."
echo "------------------------------------------------------------"

# Unmount if mounted
if mountpoint -q "$MOUNT1"; then
    echo "Unmounting $MOUNT1..."
    sudo umount "$MOUNT1"
fi

if mountpoint -q "$MOUNT2"; then
    echo "Unmounting $MOUNT2..."
    sudo umount "$MOUNT2"
fi

# Also unmount by device if mounted elsewhere
if mount | grep -q "^$DEV1 "; then
    echo "Unmounting $DEV1..."
    sudo umount "$DEV1"
fi

if mount | grep -q "^$DEV2 "; then
    echo "Unmounting $DEV2..."
    sudo umount "$DEV2"
fi

echo
read -rp "Is the LEFT USB port connected to an external drive? (y/n): " LEFT

if [[ ! "$LEFT" =~ ^[Yy]$ ]]; then
    echo
    echo "Left drive not connected."
    echo "Mount manually if required."
    exit 0
fi

read -rp "Is the RIGHT USB port connected to an external drive? (y/n): " RIGHT

if [[ ! "$RIGHT" =~ ^[Yy]$ ]]; then
    echo
    echo "Right drive not connected."
    echo "Mount manually if required."
    exit 0
fi

echo
echo "------------------------------------------------------------"
echo "Creating mount points..."
echo "------------------------------------------------------------"

sudo mkdir -p "$MOUNT1"
sudo mkdir -p "$MOUNT2"

echo
echo "------------------------------------------------------------"
echo "Mounting drives..."
echo "------------------------------------------------------------"

# Mount first drive
if [ -b "$DEV1" ]; then
    if sudo mount "$DEV1" "$MOUNT1"; then
        echo "✓ Successfully mounted $DEV1 at $MOUNT1"
    else
        echo "✗ Failed to mount $DEV1"
    fi
else
    echo "✗ Device $DEV1 does not exist."
fi

echo

# Mount second drive
if [ -b "$DEV2" ]; then
    if sudo mount "$DEV2" "$MOUNT2"; then
        echo "✓ Successfully mounted $DEV2 at $MOUNT2"
    else
        echo "✗ Failed to mount $DEV2"
    fi
else
    echo "✗ Device $DEV2 does not exist."
fi

echo
echo "------------------------------------------------------------"
echo "Current mounted external drives:"
echo "------------------------------------------------------------"

mount | grep -E "$DEV1|$DEV2"

echo
echo "Done."
