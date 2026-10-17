from flask import Blueprint

music_bp = Blueprint(
    "music",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static"
)

music_bp.app_url = "/flagship"

from . import routes
