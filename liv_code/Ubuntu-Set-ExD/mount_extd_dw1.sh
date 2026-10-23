#!/bin/bash

# Mount WD external drives at desktop login using filesystem UUIDs.

set -u

ELEMENTS_UUID="18B6B61CB6B5F9F8"
PASSPORT_UUID="1006E76C06E75170"
DUSSHERA_UUID="6B79E16875F79D68"

ELEMENTS_MOUNT="/media/Elements"
PASSPORT_MOUNT="/media/My Passport"
DUSSHERA_MOUNT="/media/Dusshera26"

USER_NAME="dkvlko"
USER_ID="$(id -u "$USER_NAME")"
GROUP_ID="$(id -g "$USER_NAME")"

echo "=========================================="
echo " External Drive Mount Utility"
echo "=========================================="

mount_ntfs() {
    local label="$1"
    local uuid="$2"
    local mountpoint="$3"

    echo
    echo "Checking $label..."

    if findmnt -rn --mountpoint "$mountpoint" >/dev/null 2>&1; then
        echo "$label is already mounted at $mountpoint"
        return 0
    fi

    if ! test -e "/dev/disk/by-uuid/$uuid"; then
        echo "WARNING: $label is not connected or its UUID is unavailable."
        return 1
    fi

    sudo mkdir -p "$mountpoint" || return 1

    if sudo mount -t ntfs-3g \
        -o "uid=$USER_ID,gid=$GROUP_ID,umask=000" \
        "UUID=$uuid" "$mountpoint"; then
        echo "Mounted $label at $mountpoint"
        return 0
    else
        echo "ERROR: Failed to mount $label"
        return 1
    fi
}

mount_ntfs "Elements" "$ELEMENTS_UUID" "$ELEMENTS_MOUNT"
mount_ntfs "My Passport" "$PASSPORT_UUID" "$PASSPORT_MOUNT"
mount_ntfs "Dusshera26" "$DUSSHERA_UUID" "$DUSSHERA_MOUNT"

echo
echo "=========================================="
echo " Mount Status"
echo "=========================================="

findmnt --mountpoint "$ELEMENTS_MOUNT" 2>/dev/null || true
findmnt --mountpoint "$PASSPORT_MOUNT" 2>/dev/null || true
findmnt --mountpoint "$DUSSHERA_MOUNT" 2>/dev/null || true

echo
echo "Done."
