from flask import Blueprint

movies_bp = Blueprint(
    "movies",
    __name__,
    template_folder="templates/movies",
    static_folder="static",
    static_url_path="/static"
)

movies_bp.app_url = "/movies"

from . import routes
