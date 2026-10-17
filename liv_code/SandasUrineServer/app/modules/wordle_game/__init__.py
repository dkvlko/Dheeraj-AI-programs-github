from flask import Blueprint

wordle_bp = Blueprint(
        "wordle",
        __name__,
        template_folder="templates",
        static_folder = "static",
        static_url_path = "/static",
        )

wordle_bp.app_url = "/wordle"

from . import routes
