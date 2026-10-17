from flask import Blueprint

notes_bp = Blueprint(
        "notesplus",
        __name__,
        template_folder= "templates",
        static_folder= "static",
        static_url_path="/static",
        )
notes_bp.app_url = "/notesplus"

from . import routes
