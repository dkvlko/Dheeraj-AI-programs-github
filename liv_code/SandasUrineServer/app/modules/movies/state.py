
from app.common import paths
import random
from pathlib import Path

_current_item = None
_previous_item = None
_next_item = None

_playlist = []
_index = 0


def update_song_pointers():
    """Update previous/current/next pointers and log them."""

    global _current_item, _previous_item, _next_item

    if not _playlist:
        return

    _current_item = _playlist[_index]

    if _index > 0:
        _previous_item = _playlist[_index - 1]
    else:
        _previous_item = None

    if _index < len(_playlist) - 1:
        _next_item = _playlist[_index + 1]
    else:
        _next_item = None

def rebuild_playlist():

    global _playlist, _index

    songs = [
        p.name
        for p in paths.DOWNLOAD_DIR.glob("*.mp3")
        if p.name.lower() != paths.AD_FILE.lower()
    ]

    random.shuffle(songs)

    playlist = []

    while songs:

        count = random.randint(3, 4)

        for _ in range(count):

            if not songs:
                break

            song = songs.pop()

            wav = paths.ANNOUNCEMENT_DIR / (Path(song).stem + ".wav")

            if wav.exists():
                playlist.append({
                    "type": "announcement",
                    "path": wav
                })

            playlist.append({
                "type": "song",
                "path": paths.DOWNLOAD_DIR / song
            })

        ad_wav = paths.ANNOUNCEMENT_DIR / (Path(paths.AD_FILE).stem + ".wav")
        ad_mp3 = paths.DOWNLOAD_DIR / paths.AD_FILE

        if ad_wav.exists():
            playlist.append({
                "type": "announcement",
                "path": ad_wav
            })

        if ad_mp3.exists():
            playlist.append({
                "type": "song",
                "path": ad_mp3
            })

    _playlist = playlist
    _index = 0
    
    update_song_pointers()

def previous_song():
    """Previous button: jump to the previous song's announcement."""

    global _index

    if not _playlist:
        rebuild_playlist()

    # Start searching before the current item.
    i = _index - 1

    # If currently on a song, skip its own announcement.
    if (
        _playlist[_index]["type"] == "song"
        and i >= 0
        and _playlist[i]["type"] == "announcement"
    ):
        i -= 1

    while i >= 0:
        if _playlist[i]["type"] == "announcement":
            _index = i
            return
        i -= 1

    _index = 0

    update_song_pointers()

def next_song():
    """Next button: jump to the next announcement."""

    global _index
    found = False
    if not _playlist:
        rebuild_playlist()

    i = _index + 1

    while i < len(_playlist):

        if _playlist[i]["type"] == "announcement":
            _index = i
            found = True
            break

        i += 1

    # End of playlist
    if not found:
        rebuild_playlist()

    update_song_pointers()

def advance_song():
    """Normal playback: advance to the next playlist item."""

    global _index

    if not _playlist:
        rebuild_playlist()

    _index += 1

    if _index >= len(_playlist):
        rebuild_playlist()
    
    update_song_pointers()


def current_song():
    global _index

    if not _playlist:
        rebuild_playlist()

    if _index >= len(_playlist):
        rebuild_playlist()
    return _playlist[_index]["path"]

