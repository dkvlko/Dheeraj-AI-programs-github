from flask import Blueprint

lanmaps_bp=Blueprint(
        "lan_maps",
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
        )

lanmaps_bp.app_url = "/lan_maps"

from . import routes
