from flask import Blueprint

ziintrdata_bp = Blueprint(
    "ziintrdata",
    __name__,
    template_folder="templates/intrdata",
    static_folder="static",
    static_url_path="/static"
)

ziintrdata_bp.app_url = "/ziintrdata"

from . import routes
