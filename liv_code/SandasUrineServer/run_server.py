from app import create_app
from app.config import Config
from app.common.paths import (
    SERVER_CERT,
    SERVER_KEY,
)
from app.extensions import socketio


app = create_app()


if __name__ == "__main__":

    socketio.run(
        app,
        host=Config.SERVER_HOST,
        port=Config.SERVER_PORT,
        debug=Config.DEBUG,
        ssl_context=(
            str(SERVER_CERT),
            str(SERVER_KEY)
        )
    )
