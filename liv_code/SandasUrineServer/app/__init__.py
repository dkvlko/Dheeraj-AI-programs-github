from flask import Flask

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

    return app
