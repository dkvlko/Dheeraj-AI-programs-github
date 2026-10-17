
from flask import Blueprint

clock_bp = Blueprint(
    "clock_lap",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

clock_bp.app_url = "/clock_lap"

from . import routes
