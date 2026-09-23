TV Remote blueprint for the existing Flask-SocketIO application.

Directory:

app/tv_remote/
    __init__.py
    routes.py
    templates/tvremote.html
    static/tvremote.js
    static/tvremote.css

The blueprint follows the same pattern as the existing remote_lap app.

The routes.py talks to:

    /run/tvandroidremote/remote.sock

The Android-TV daemon remains responsible for ADB and connection
management.

Blueprint registration should follow the existing create_app()
architecture used by the application.

The page URL is intended to be:

    /tv_remote/

The browser uses the application's existing socket.io.min.js.

Custom app buttons use:

    {"command": "launch_app", "package": "..."}

The daemon must already implement launch_app as discussed.
