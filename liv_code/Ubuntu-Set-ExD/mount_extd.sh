#!/bin/bash

##############################################################################
# Mount WD External Drives
# Drives are identified by filesystem UUID.
##############################################################################

ELEMENTS_UUID="18B6B61CB6B5F9F8"
PASSPORT_UUID="1006E76C06E75170"

ELEMENTS_MOUNT="/media/Elements"
PASSPORT_MOUNT="/media/My Passport"

echo
echo "============================================================"
echo "        WD External Drive Mount Utility"
echo "============================================================"
echo

##############################################################################
# Create mount points
##############################################################################

sudo mkdir -p "$ELEMENTS_MOUNT"
sudo mkdir -p "$PASSPORT_MOUNT"

##############################################################################
# Mount Elements
##############################################################################

echo "Mounting Elements..."

#if sudo mount UUID="$ELEMENTS_UUID" "$ELEMENTS_MOUNT"; then
#    echo "✓ Elements mounted successfully."
#    echo "  UUID      : $ELEMENTS_UUID"
#    echo "  Mount     : $ELEMENTS_MOUNT"
#else
#    echo "✗ Failed to mount Elements."
#fi
if sudo mount -t ntfs-3g UUID="$ELEMENTS_UUID" "$ELEMENTS_MOUNT" \
    -o uid=$(id -u dkvlko),gid=$(id -g dkvlko),umask=000; then
    echo "✓ ELEMENTS  mounted successfully."
    echo "  UUID      : $ELEMENTS_UUID"
    echo "  Mount     : $ELEMENTS_MOUNT"
else
    echo "✗ Failed to mount ELEMENTS."
fi

echo

##############################################################################
# Mount My Passport
##############################################################################

echo "Mounting My Passport..."

#if sudo mount UUID="$PASSPORT_UUID" "$PASSPORT_MOUNT"; then
#    echo "✓ My Passport mounted successfully."
#    echo "  UUID      : $PASSPORT_UUID"
#    echo "  Mount     : $PASSPORT_MOUNT"
#else
#    echo "✗ Failed to mount My Passport."
#fi

if sudo mount -t ntfs-3g UUID="$PASSPORT_UUID" "$PASSPORT_MOUNT" \
    -o uid=$(id -u dkvlko),gid=$(id -g dkvlko),umask=000; then
    echo "✓ My Passport mounted successfully."
    echo "  UUID      : $PASSPORT_UUID"
    echo "  Mount     : $PASSPORT_MOUNT"
else
    echo "✗ Failed to mount My Passport."
fi

echo

##############################################################################
# Display status
##############################################################################

echo "============================================================"
echo "                 Mount Status"
echo "============================================================"

echo
echo "Elements:"
findmnt "$ELEMENTS_MOUNT" 2>/dev/null || echo "Not mounted."

echo
echo "My Passport:"
findmnt "$PASSPORT_MOUNT" 2>/dev/null || echo "Not mounted."

echo
echo "============================================================"
echo "Done."
echo "============================================================"
