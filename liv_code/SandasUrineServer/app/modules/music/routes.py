from flask import render_template

from . import music_bp


@flagship_bp.route("/flagship")
def flagship():
    return render_template("flagship.html")
