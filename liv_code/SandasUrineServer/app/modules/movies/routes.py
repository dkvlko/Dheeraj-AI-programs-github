from flask import (
    request,
    render_template,
    send_file,
    Response,
    abort,
    current_app,
)

from pathlib import Path
import random
import urllib.parse
from urllib.parse import quote

from app.common import paths
from . import state
from . import movies_bp
import subprocess


# ---------------------------------------------------------
# Movie configuration
# ---------------------------------------------------------

MOVIE_DIR = Path("/media/Elements/MegaDump_720p")

MOVIE_STATUS_FILE = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/"
    "live_code/SandasUrineServer/app/modules/movies/"
    "static/moviestatus.txt"
)

MOVIE_SERVER_URL = "https://192.168.0.25:8000"

TV_DEVICE = "192.168.0.100:5555"

ADVT_MOVIE = (
    "/media/Elements/MegaDump_720p/"
    "Andaz.Apna.Apna.[1994].1080p.10bit.Bluray.x265."
    "Hindi.AAC.5.1.Esub.[-=BlacK_PearL=-].mp4"
)


#Launch movie #
def launch_movie_on_tv(movie_path):

    movie_name = Path(movie_path).name

    movie_url = (
        f"{MOVIE_SERVER_URL}/movies/stream/"
        + quote(movie_name, safe="")
    )

    command = [
        "adb",
        "-s",
        TV_DEVICE,
        "shell",
        "am",
        "start",
        "-a",
        "android.intent.action.VIEW",
        "-d",
        movie_url,
        "-t",
        "video/mp4",
        "-p",
        "org.videolan.vlc",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=15,
    )

    output = result.stdout.strip()

    if result.stderr:
        output += "\n" + result.stderr.strip()

    return result.returncode == 0, output
# ---------------------------------------------------------
# Movie status file
# ---------------------------------------------------------

def load_movie_status():
    """
    Read moviestatus.txt.

    Format:

        advt=0
        /full/path/movie1.mp4|not-seen
        /full/path/movie2.mp4|seen
    """

    movies = {}
    advt = 0

    if not MOVIE_STATUS_FILE.exists():
        return advt, movies

    with MOVIE_STATUS_FILE.open("r", encoding="utf-8") as f:

        for line in f:
            line = line.strip()

            if not line:
                continue

            if line.startswith("advt="):
                try:
                    advt = int(line.split("=", 1)[1])
                except ValueError:
                    advt = 0

                continue

            if "|" not in line:
                continue

            filename, status = line.rsplit("|", 1)

            filename = filename.strip()
            status = status.strip()

            if filename:
                movies[filename] = status

    return advt, movies


def save_movie_status(advt, movies):
    """
    Save moviestatus.txt.
    """

    MOVIE_STATUS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with MOVIE_STATUS_FILE.open("w", encoding="utf-8") as f:

        f.write(f"advt={advt}\n")

        for filename in sorted(movies):
            f.write(f"{filename}|{movies[filename]}\n")


def initialize_movie_status():
    """
    Create the movie status file if it does not exist,
    using every MP4 file in MOVIE_DIR.
    """

    mp4_files = sorted(
        p for p in MOVIE_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".mp4"
    )

    movies = {
        str(path): "not-seen"
        for path in mp4_files
    }

    advt = 0

    save_movie_status(advt, movies)

    return advt, movies


# ---------------------------------------------------------
# Landing page
# ---------------------------------------------------------

@movies_bp.route("/")
def movies_home():
    return render_template("movies.html")


# ---------------------------------------------------------
# Browser movie page
# ---------------------------------------------------------

@movies_bp.route("/show_movie")
def show_movie():
    # -----------------------------------------------------
    # 1. Load/create movie status
    # -----------------------------------------------------

    if not MOVIE_STATUS_FILE.exists():
        advt, movies = initialize_movie_status()
    else:
        advt, movies = load_movie_status()

    # -----------------------------------------------------
    # 2. Add any newly discovered MP4 files
    # -----------------------------------------------------

    current_files = {
        str(path)
        for path in MOVIE_DIR.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".mp4"
    }

    for filename in current_files:
        if filename not in movies:
            movies[filename] = "not-seen"

    # -----------------------------------------------------
    # 3. Find unseen movies
    # -----------------------------------------------------

    unseen_movies = [
        filename
        for filename, status in movies.items()
        if status == "not-seen"
        and Path(filename).exists()
    ]

    # -----------------------------------------------------
    # 4. Start a new cycle if everything has been seen
    # -----------------------------------------------------

    if not unseen_movies:
        for filename in movies:
            movies[filename] = "not-seen"

        unseen_movies = [
            filename
            for filename in movies
            if Path(filename).exists()
            and Path(filename).suffix.lower() == ".mp4"
        ]

    if not unseen_movies:
        return (
            "No MP4 movies found in movie directory.",
            404
        )

    # -----------------------------------------------------
    # 5. Select random unseen movie
    # -----------------------------------------------------

    selected_movie = random.choice(unseen_movies)

    # -----------------------------------------------------
    # 6. Advertisement/movie substitution
    # -----------------------------------------------------

    movie_to_play = selected_movie

    if advt >= 3:
        random_number = random.random()

        if random_number > 0.5:
            movie_to_play = ADVT_MOVIE

    # -----------------------------------------------------
    # 7. Create browser streaming URL
    # -----------------------------------------------------

    movie_name = Path(movie_to_play).name

    movie_url = (
        f"{MOVIE_SERVER_URL}/movies/stream/"
        + quote(movie_name, safe="")
    )

    # -----------------------------------------------------
    # 8. Render browser player
    # -----------------------------------------------------

    return render_template(
        "show_movie.html",
        movie=movie_name,
        movie_url=movie_url
    )

# ---------------------------------------------------------
# Generic movie streaming route
# ---------------------------------------------------------

@movies_bp.route("/stream/<path:filename>")
def stream_movie(filename):
    print("========== STREAM REQUEST ==========")
    print("filename:", repr(filename))

    movie_path = MOVIE_DIR / filename

    print("movie_path:", repr(str(movie_path)))
    print("exists:", movie_path.exists())
    print("is_file:", movie_path.is_file())
    print("suffix:", repr(movie_path.suffix))

    if not movie_path.exists():
        print("FILE DOES NOT EXIST")
        abort(404)

    if not movie_path.is_file():
        print("NOT A FILE")
        abort(404)

    if movie_path.suffix.lower() != ".mp4":
        print("NOT MP4")
        abort(404)

    print("SENDING FILE")
    print("====================================")

    return send_file(
        movie_path,
        mimetype="video/mp4",
        conditional=True
    )
# ---------------------------------------------------------
# Launch movie on Android TV / VLC
# ---------------------------------------------------------

@movies_bp.route("/show_movie_tv")
def show_movie_tv():

    # -----------------------------------------------------
    # 1. Load/create movie status
    # -----------------------------------------------------

    if not MOVIE_STATUS_FILE.exists():

        advt, movies = initialize_movie_status()

    else:

        advt, movies = load_movie_status()


    # -----------------------------------------------------
    # 2. Make sure all currently existing MP4 files
    #    are present in the status file
    # -----------------------------------------------------

    current_files = {
        str(path)
        for path in MOVIE_DIR.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".mp4"
    }

    for filename in current_files:

        if filename not in movies:
            movies[filename] = "not-seen"


    # -----------------------------------------------------
    # 3. Find unseen movies
    # -----------------------------------------------------

    unseen_movies = [
        filename
        for filename, status in movies.items()
        if status == "not-seen"
        and Path(filename).exists()
    ]


    # -----------------------------------------------------
    # 4. If everything has been seen, start a new cycle
    # -----------------------------------------------------

    if not unseen_movies:

        for filename in movies:
            movies[filename] = "not-seen"

        unseen_movies = [
            filename
            for filename in movies
            if Path(filename).exists()
            and Path(filename).suffix.lower() == ".mp4"
        ]


    if not unseen_movies:

        return (
            "No MP4 movies found in movie directory.",
            404
        )


    # -----------------------------------------------------
    # 5. Select random unseen movie
    # -----------------------------------------------------

    selected_movie = random.choice(unseen_movies)


    # -----------------------------------------------------
    # 6. Advertisement/movie substitution
    # -----------------------------------------------------

    movie_to_play = selected_movie

    if advt >= 3:

        random_number = random.random()

        if random_number > 0.5:
            movie_to_play = ADVT_MOVIE
            advt=0


  # Launch VLC through ADB
    ok, output = launch_movie_on_tv(movie_to_play)



    # -----------------------------------------------------
    # 10. Only update status after launch request
    #     was successfully accepted.
    # -----------------------------------------------------

    if ok:

        # The originally selected movie is marked seen.
        movies[selected_movie] = "seen"

        # Advertisement counter increments every launch.
        advt += 1

        save_movie_status(advt, movies)


    # -----------------------------------------------------
    # 11. Show confirmation page
    # -----------------------------------------------------

    return render_template(
        "show_movie_tv.html",
        ok=ok,
        movie=Path(movie_to_play).name,
        output=output
    )
