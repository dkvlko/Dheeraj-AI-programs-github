#!/usr/bin/env python3

from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
import subprocess

# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------

MUSIC_DIR = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/SpotifyMusicRIP"
)

ANNOUNCEMENT_DIR = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Announcements"
)

PIPER = "/home/dkvlko/piper/piper/piper"

VOICE = "/home/dkvlko/piper/en_US-lessac-medium.onnx"

ANNOUNCEMENT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------


def song_metadata(mp3_file):

    result = {
        "title": mp3_file.stem,
        "album": "",
        "artist": ""
    }

    try:

        tags = EasyID3(mp3_file)

        result["title"] = tags.get("title", [mp3_file.stem])[0]
        result["album"] = tags.get("album", [""])[0]
        result["artist"] = tags.get("artist", [""])[0]

    except Exception:

        try:
            audio = MP3(mp3_file)

            if audio.get("TIT2"):
                result["title"] = audio["TIT2"].text[0]

            if audio.get("TALB"):
                result["album"] = audio["TALB"].text[0]

            if audio.get("TPE1"):
                result["artist"] = audio["TPE1"].text[0]

        except Exception:
            pass

    return result


def build_sentence(meta):

    sentence = "Now playing "

    sentence += meta["title"]

    if meta["album"]:
        sentence += ". From the album " + meta["album"]

    if meta["artist"]:
        sentence += ". Sung by " + meta["artist"]

    sentence += "."

    return sentence


def create_wav(sentence, wav_file):

    subprocess.run(
        [
            PIPER,
            "--model",
            VOICE,
            "--output_file",
            str(wav_file)
        ],
        input=sentence,
        text=True,
        check=True
    )


def main():

    mp3_files = sorted(MUSIC_DIR.glob("*.mp3"))

    print(f"Found {len(mp3_files)} mp3 files.\n")

    generated = 0
    skipped = 0

    for mp3 in mp3_files:

        wav = ANNOUNCEMENT_DIR / (mp3.stem + ".wav")

        if wav.exists():
            print(f"Skipping : {wav.name}")
            skipped += 1
            continue

        meta = song_metadata(mp3)

        sentence = build_sentence(meta)

        print(sentence)

        create_wav(sentence, wav)

        generated += 1

    print()
    print(f"Generated : {generated}")
    print(f"Skipped   : {skipped}")


if __name__ == "__main__":
    main()
