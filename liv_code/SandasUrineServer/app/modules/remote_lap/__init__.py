from flask import Blueprint

remotelap_bp = Blueprint(
    "remote_lap",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

remotelap_bp.app_url = "/remote_lap"

from . import routes

