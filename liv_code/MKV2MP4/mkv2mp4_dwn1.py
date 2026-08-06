#!/usr/bin/env python3
"""
Batch MKV -> 720p MP4 converter using FFmpeg + NVIDIA NVENC.

Input : /media/Elements/MegaDump
Output: /media/Elements/MegaDump_720p

Features
--------
- Recursive scan
- Preserves folder structure
- Uses h264_nvenc for video
- Resizes to 720p
- Copies all audio streams, subtitles, chapters and metadata
- Skips existing outputs
- Logs progress
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

SOURCE_DIR = Path("/media/Elements/MegaDumpTest")
OUTPUT_DIR = Path("/media/Elements/MegaDumpTest_720p")

VIDEO_CODEC = "hevc_nvenc"
CQ = "27"
PRESET = "p5"

LOG_FILE = OUTPUT_DIR / "conversion.log"


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def human(n: int) -> str:
    s = float(n)
    for u in ("B","KB","MB","GB","TB"):
        if s < 1024 or u=="TB":
            return f"{s:.2f} {u}"
        s /= 1024


def ffmpeg_exists():
    return shutil.which("ffmpeg") is not None


def convert(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i", str(src),

        "-map", "0",
        "-vf", "scale=-2:720,format=yuv420p",

        "-c:v", VIDEO_CODEC,
        "-profile:v","main",
        "-rc", "vbr",
        "-cq", CQ,
        "-b:v", "0",
        "-preset", PRESET,

        "-c:a", "copy",
        "-c:s", "mov_text",
        "-map_metadata", "0",
        "-map_chapters", "0",
        "-movflags", "+faststart",

        str(dst),
    ]

    return subprocess.run(cmd).returncode == 0


def main():
    if not ffmpeg_exists():
        print("ffmpeg not found.")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(SOURCE_DIR.rglob("*.mkv"))

    if not files:
        print("No MKV files found.")
        return 0

    total_before = 0
    total_after = 0
    converted = skipped = failed = 0
    start = time.time()

    log(f"Found {len(files)} MKV files")

    for i, src in enumerate(files, 1):
        rel = src.relative_to(SOURCE_DIR)
        dst = (OUTPUT_DIR / rel).with_suffix(".mp4")

        total_before += src.stat().st_size

        if dst.exists():
            skipped += 1
            total_after += dst.stat().st_size
            log(f"[{i}/{len(files)}] SKIP {rel}")
            continue

        log(f"[{i}/{len(files)}] START {rel}")

        t0 = time.time()
        ok = convert(src, dst)
        elapsed = time.time() - t0

        if ok and dst.exists():
            converted += 1
            new_size = dst.stat().st_size
            total_after += new_size
            saved = src.stat().st_size - new_size
            pct = saved / src.stat().st_size * 100
            log(
                f"DONE {rel} | "
                f"{human(src.stat().st_size)} -> {human(new_size)} | "
                f"Saved {human(saved)} ({pct:.1f}%) | "
                f"{elapsed:.1f}s"
            )
        else:
            failed += 1
            log(f"FAILED {rel}")

    duration = time.time() - start

    log("=" * 70)
    log(f"Converted : {converted}")
    log(f"Skipped   : {skipped}")
    log(f"Failed    : {failed}")
    log(f"Original  : {human(total_before)}")
    log(f"Output    : {human(total_after)}")
    if total_before:
        log(f"Saved     : {human(total_before-total_after)}")
    log(f"Elapsed   : {duration/3600:.2f} hours")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
