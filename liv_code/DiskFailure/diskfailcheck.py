#!/usr/bin/env python3

from datetime import datetime
from pathlib import Path
import time

# External disk mount point
DISK_DIR = Path("/media/My Passport")

# File on the external disk
DISK_LOG = DISK_DIR / "disklog.txt"

# Failure log in the user's home directory
FAILURE_LOG = Path.home() / "diskfailure.txt"

INTERVAL = 1 * 30  # 30 sec


def write_failure(message):
    """Write a failure message to ~/diskfailure.txt."""
    try:
        timestamp = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )

        with FAILURE_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{timestamp} - {message}\n")

    except Exception:
        # If even the failure log cannot be written, there is
        # nothing useful the program can do.
        pass


def write_disk_log():
    """Write the current local timestamp to the external disk."""
    try:
        timestamp = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )

        with DISK_LOG.open("a", encoding="utf-8") as f:
            f.write(timestamp + "\n")

            # Force Python's buffered data to the OS.
            f.flush()

            # Optionally force the OS to commit the data.
            # This makes the test more meaningful for a removable disk.
            import os
            os.fsync(f.fileno())

        return True

    except Exception as e:
        write_failure(
            f"Failed to write to {DISK_LOG}: "
            f"{type(e).__name__}: {e}"
        )
        return False


def main():
    while True:
        write_disk_log()
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
