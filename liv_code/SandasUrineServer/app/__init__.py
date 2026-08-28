from flask import Flask
from flask_socketio import test_client

from .common.paths import (
    TEMPLATE_FOLDER,
    STATIC_FOLDER,
)

from .extensions import socketio


def create_app():

    app = Flask(
        __name__,
        template_folder=TEMPLATE_FOLDER,
        static_folder=STATIC_FOLDER,
        static_url_path="/static"
    )

    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode="threading"
    )

    # Register application modules here.
    #from .modules.music import music_bp

    #app.register_blueprint(music_bp)

    from .modules.testbp import test_bp
    from app.common.blueprint_browser import blueprint_browser


    app.register_blueprint(
        blueprint_browser
    )
    app.register_blueprint(
        test_bp,
        url_prefix=test_bp.app_url
    )


    return app

