from flask import Blueprint

tvremote_bp = Blueprint(
    "tvremote",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

tvremote_bp.app_url = "/tv_remote"

from . import routes
