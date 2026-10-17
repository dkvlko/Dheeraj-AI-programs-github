
from flask import (request, 
                   render_template,
                   send_file,
                   Response,
                   abort,
                   current_app,
)

from pathlib import Path
import random
from app.common import paths
from . import  state 
from . import music_bp


@music_bp.route("/")
def flagship():

    ua = request.headers.get("User-Agent", "")

    if "iPad" in ua and "CPU OS 12_" in ua:
        return render_template("music/flagship_mini2.html")

    return render_template("music/flagship.html")


@music_bp.route("/current")
def flagship_current():

    path = state.current_song()          # <-- Now returns a Path object
    try:

        if not path.exists():
            current_app.logger.error("Audio file not found: %s", path)
            abort(404, description=f"Audio file not found: {path}")

        mimetype = "audio/wav" if path.suffix.lower() == ".wav" else "audio/mpeg"

        file_size = path.stat().st_size
        range_header = request.headers.get("Range")

        if not range_header:
            return send_file(
                path,
                mimetype=mimetype,
                conditional=True,
            )

        start, end = range_header.replace("bytes=", "").split("-")

        start = int(start)
        end = file_size - 1 if end == "" else int(end)

        length = end - start + 1

        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        response = Response(
            data,
            206,
            mimetype=mimetype,
            direct_passthrough=True,
        )

        response.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Content-Length"] = str(length)

        return response
    except Exception as e:
        current_app.logger.exception("Error serving %s", path)
        abort(500, description=str(e))

@music_bp.route("/advance")
def flagship_advance():

    state.advance_song()

    #app.logger.info("Now playing %s", current_song())

    return ("", 204)

@music_bp.route("/next")
def flagship_next():
    state.next_song()
    #app.logger.info("Now playing %s", current_song())
    return ("", 204)

@music_bp.route("/previous")
def flagship_previous():

    state.previous_song()

    #app.logger.info("Now playing %s", current_song())

    return ("", 204)

@music_bp.route("/status")
def flagship_status():

    return {
        "previous": None if state._previous_item is None else state._previous_item["path"].name,
        "current": None if state._current_item is None else state._current_item["path"].name,
        "next": None if state._next_item is None else state._next_item["path"].name,
    }
