from flask import Blueprint

lancloud_bp = Blueprint(
    "lan_cloud",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static"
)

lancloud_bp.app_url = "/lan_cloud"

from . import routes
