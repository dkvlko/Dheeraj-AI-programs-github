#!/usr/bin/env python3

from pathlib import Path
import shutil
import hashlib
import logging
import sys
import time
from liv_code.MKV2MP4 import mkv2mp4_cpu
from mkv2mp4_cpu import convmkv2mp4

SOR_DIR = Path("/media/Elements/MegaDump")
DEST_DIR = Path("/data/MegaDump")

FILES_PER_BATCH = 5
BUFFER_SIZE = 16 * 1024 * 1024  # 16 MiB
VERIFY_AFTER_COPY = True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger(__name__)


def sha256_file(path: Path) -> str:
    """
    Calculate SHA-256 checksum of a file.
    """

    sha256 = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            data = f.read(BUFFER_SIZE)

            if not data:
                break

            sha256.update(data)

    return sha256.hexdigest()


def copy_and_verify(source: Path, destination: Path) -> bool:
    """
    Copy source to destination and optionally verify using SHA-256.

    The source is NOT deleted here.
    """

    temp_destination = destination.with_name(
        destination.name + ".part"
    )

    try:
        log.info("Copying:")
        log.info("  SOURCE: %s", source)
        log.info("  DEST:   %s", destination)

        # Remove stale .part file if one exists.
        if temp_destination.exists():
            log.warning(
                "Removing stale temporary file: %s",
                temp_destination,
            )
            temp_destination.unlink()

        # Copy to temporary destination first.
        with source.open("rb") as src:
            with temp_destination.open("wb") as dst:

                while True:
                    buffer = src.read(BUFFER_SIZE)

                    if not buffer:
                        break

                    dst.write(buffer)

                # Flush Python's buffers.
                dst.flush()

        # Ask the OS to flush the file to the storage device.
        with temp_destination.open("rb") as f:
            import os
            os.fsync(f.fileno())

        # Check file sizes before checksum verification.
        source_size = source.stat().st_size
        destination_size = temp_destination.stat().st_size

        if source_size != destination_size:
            raise IOError(
                f"Size mismatch: "
                f"source={source_size}, "
                f"destination={destination_size}"
            )

        if VERIFY_AFTER_COPY:
            log.info("Verifying SHA-256...")

            source_hash = sha256_file(source)
            destination_hash = sha256_file(temp_destination)

            if source_hash != destination_hash:
                raise IOError(
                    "SHA-256 verification FAILED"
                )

            log.info("SHA-256 verification successful.")

        # Rename .part → final filename.
        # This is an atomic operation on the same filesystem.
        temp_destination.replace(destination)

        log.info("Copy completed successfully.")

        return True

    except Exception:
        log.exception(
            "COPY FAILED: %s",
            source,
        )

        # Never leave a partial file pretending to be complete.
        try:
            if temp_destination.exists():
                temp_destination.unlink()
        except Exception:
            log.exception(
                "Could not remove temporary file: %s",
                temp_destination,
            )

        return False


def process_batch(files: list[Path]) -> bool:
    """
    Process one batch of files.

    Returns True if every file in the batch was successfully
    copied, verified and deleted.
    """

    for source in files:

        destination = DEST_DIR / source.name

        log.info("=" * 70)
        log.info("Processing: %s", source.name)

        try:
            # If destination already exists, do NOT blindly overwrite it.
            if destination.exists():

                source_size = source.stat().st_size
                destination_size = destination.stat().st_size

                if source_size == destination_size:
                    log.warning(
                        "Destination already exists with same size."
                    )

                    if VERIFY_AFTER_COPY:
                        log.info(
                            "Verifying existing destination..."
                        )

                        source_hash = sha256_file(source)
                        destination_hash = sha256_file(destination)

                        if source_hash == destination_hash:
                            log.info(
                                "Existing destination verified."
                            )
                            log.info(
                                "Deleting source: %s",
                                source,
                            )

                            source.unlink()

                            log.info(
                                "Source deleted successfully."
                            )

                            continue

                raise FileExistsError(
                    f"Destination already exists and "
                    f"could not be safely verified: {destination}"
                )

            # Copy + verify.
            success = copy_and_verify(
                source,
                destination,
            )

            if not success:
                log.error(
                    "Stopping batch because copy failed."
                )
                return False

            # Only delete source AFTER successful copy + verification.
            log.info(
                "Deleting source: %s",
                source,
            )

            source.unlink()

            log.info(
                "Source deleted successfully."
            )

        except Exception:
            log.exception(
                "ERROR processing: %s",
                source,
            )

            log.error(
                "Source file has NOT been deleted."
            )

            return False

    return True


def get_files() -> list[Path]:
    """
    Return regular files from SOR_DIR.

    Temporary .part files are ignored.
    """

    return sorted(
        (
            p
            for p in SOR_DIR.iterdir()
            if p.is_file()
            and not p.name.endswith(".part")
        ),
        key=lambda p: p.name,
    )


def main() -> int:

    log.info("Starting MegaDump migration.")

    log.info("Source:      %s", SOR_DIR)
    log.info("Destination: %s", DEST_DIR)

    # Basic checks.
    if not SOR_DIR.exists():
        log.error(
            "Source directory does not exist: %s",
            SOR_DIR,
        )
        return 1

    if not SOR_DIR.is_dir():
        log.error(
            "Source is not a directory: %s",
            SOR_DIR,
        )
        return 1

    try:
        DEST_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )
    except Exception:
        log.exception(
            "Could not create destination directory."
        )
        return 1

    batch_number = 0

    while True:

        files = get_files()

        if not files:
            log.info("=" * 70)
            log.info("SOURCE DIRECTORY IS EMPTY.")
            log.info("Migration completed successfully.")
            log.info("=" * 70)
            break

        batch_number += 1

        batch = files[:FILES_PER_BATCH]

        log.info("=" * 70)
        log.info(
            "BATCH %d: %d file(s)",
            batch_number,
            len(batch),
        )

        for file in batch:
            try:
                size_gb = file.stat().st_size / (1024 ** 3)

                log.info(
                    "  %s (%.2f GiB)",
                    file.name,
                    size_gb,
                )

            except OSError:
                log.warning(
                    "Could not determine size: %s",
                    file,
                )

        # Process the batch.
        success = process_batch(batch)

        if not success:
            log.error("=" * 70)
            log.error(
                "BATCH FAILED."
            )
            log.error(
                "Stopping to protect your data."
            )
            log.error("=" * 70)

            return 2

        log.info(
            "BATCH %d COMPLETED.",
            batch_number,
        )

        # Give the external drive a moment between batches.
        time.sleep(2)
# Calling mkv2mp4 conversion python process
        mkv2mp4_cpu.convmkv2mp4()
    return 0


if __name__ == "__main__":
    sys.exit(main())
