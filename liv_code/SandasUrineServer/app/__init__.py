from flask import Flask
from flask_socketio import test_client

#from flask_socketio import SocketIO

#from .common.paths import (
#    TEMPLATE_FOLDER,
#    STATIC_FOLDER,
#)

from .extensions import socketio


def create_app():

    app = Flask(
        __name__,
        #template_folder=TEMPLATE_FOLDER,
        #static_folder=STATIC_FOLDER,
        #static_url_path="/static"
    )

    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode="threading"
    )


    app.jinja_env.auto_reload = True
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    # Register application modules here.
    #from .modules.music import music_bp

    #app.register_blueprint(music_bp)

    from .modules.testbp import test_bp
    from app.common.blueprint_browser import blueprint_browser


    app.register_blueprint(
        blueprint_browser
    )

    #app.register_blueprint(
    #    test_bp,
    #    url_prefix=test_bp.app_url
    #)

    from app.modules.music import music_bp
    app.register_blueprint(
        music_bp,
        url_prefix=music_bp.app_url
    )


    from app.modules.lan_cloud import lancloud_bp
    app.register_blueprint(
        lancloud_bp,
        url_prefix=lancloud_bp.app_url
    )


    from app.modules.lan_maps import lanmaps_bp
    app.register_blueprint(
        lanmaps_bp,
        url_prefix=lanmaps_bp.app_url
    )


    from app.modules.remote_lap import remotelap_bp
    #from app.modules.remote_lap.routes import register_socket_handlers 

    app.register_blueprint(
        remotelap_bp,
        url_prefix=remotelap_bp.app_url
    )


    from app.modules.clock_lap import clock_bp
    app.register_blueprint(
        clock_bp,
        url_prefix=clock_bp.app_url
    )

    #print("Static folder:", app.static_folder)
    #Static folder: /home/dkvlko/Dheeraj-AI-programs-github/liv_code/SandasUrineServer/app/static
    #Static URL path: /static
    #print("Static URL path:", app.static_url_path)

    return app

