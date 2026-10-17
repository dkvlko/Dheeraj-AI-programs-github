from flask import Blueprint

dailylog_bp = Blueprint(
    "dailylog",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

dailylog_bp.app_url="/dailylog"

from . import routes
