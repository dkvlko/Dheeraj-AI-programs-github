from flask import render_template
from flask_socketio import emit
from . import clock_bp
from . import static
from app import socketio

@clock_bp.route("/")
def clocklap():
    return render_template("clock.html")

@clock_bp.route("/details_date.html")
def details_date():
    return render_template("details_date.html")
