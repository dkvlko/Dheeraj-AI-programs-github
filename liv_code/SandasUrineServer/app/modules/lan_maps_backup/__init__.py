from flask import Blueprint

lanmapsv2_bp=Blueprint(
        "lan_mapsv2",
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/static",
        )

lanmapsv2_bp.app_url = "/lan_maps_v2"

from . import routes
