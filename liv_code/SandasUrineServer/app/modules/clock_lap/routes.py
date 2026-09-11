from flask import render_template
from flask_socketio import emit
from . import clock_bp
from . import static
from app import socketio
import shutil
from pathlib import Path
MODULE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR =MODULE_DIR / "templates"


@clock_bp.route("/")
def clocklap():
    return render_template("clock.html")

@clock_bp.route("/details_date.html")
def details_date():
    response = render_template("details_date.html")

    return response, 200, {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    }
