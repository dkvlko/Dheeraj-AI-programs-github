I have following directory structure(based on Application Factory model)
python files which will be ported from a different folder.
I will give you the app main url handler,its related function, 
its related html and javascript file names, please suggest me where to put
them in the directory, I am also providing the server code used in the
new server location,the main url handler of the app is /flagship and it 
sends file flagship.html:
dkvlko@dkvlko-HP-ENVY-15-Notebook-PC:~/live_code/SandasUrineServer$ tree -d
.
├── app
│   ├── common
│   └── modules
│       ├── dailylog
│       │   ├── static
│       │   └── templates
│       ├── lan_cloud
│       ├── music
│       │   ├── static
│       │   └── templates
│       └── remote_mouse
│           ├── static
│           └── templates
├── BLOBS
│   ├── Announcements
│   └── Icons
├── logs
├── secrets
├── static
│   └── common
└── tests
    ├── common
    ├── dailylog
    ├── music
    └── remote_mouse

26 directories
dkvlko@dkvlko-HP-ENVY-15-Notebook-PC:~/live_code/SandasUrineServer$ 
================================
location: .(Root)
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
    ============================
location:./app

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
