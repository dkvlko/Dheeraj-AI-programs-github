from flask import render_template
from flask_socketio import emit
from . import tvremote_bp
from app import socketio

import json
import socket

# Flask only talks to its Unix-domain command socket.
TV_REMOTE_SOCKET = "/run/tvandroidremote/remote.sock"


class TVRemoteError(RuntimeError):
    pass


def send_tv_command(command, **kwargs):
    """
    Send one JSON command to tvandroidremote.service.

    The daemon is responsible for:
      - discovering the TV
      - reconnecting every 30 minutes/checking availability
    """
    request = {
        "command": command,
        **kwargs,
    }

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5)

    try:
        sock.connect(TV_REMOTE_SOCKET)
        sock.sendall((json.dumps(request) + "\n").encode("utf-8"))

        response_data = b""

        while not response_data.endswith(b"\n"):
            chunk = sock.recv(4096)

            if not chunk:
                break

            response_data += chunk

        if not response_data:
            raise TVRemoteError(
                "No response from Android TV remote service"
            )

        response = json.loads(
            response_data.decode("utf-8")
        )

        if not response.get("ok", False):
            raise TVRemoteError(
                response.get(
                    "error",
                    "Android TV command failed"
                )
            )

        return response

    except socket.timeout as exc:
        raise TVRemoteError(
            "Android TV remote service timed out"
        ) from exc

    except OSError as exc:
        raise TVRemoteError(
            "Android TV remote service unavailable: "
            + str(exc)
        ) from exc

    except json.JSONDecodeError as exc:
        raise TVRemoteError(
            "Invalid response from Android TV remote service"
        ) from exc

    finally:
        sock.close()


# ------------------------------------------------------------
# HTTP page
# ------------------------------------------------------------

@tvremote_bp.route("/")
def tvremote():
    return render_template("tvremote/tvremote.html")


# ------------------------------------------------------------
# Socket.IO commands
# ------------------------------------------------------------

@socketio.on("tv_remote_command")
def handle_tv_remote_command(data):
    """
    Generic TV remote command.

    Browser sends, for example:

        socket.emit("tv_remote_command",
                    {"command": "up"})

    or:

        {"command": "launch_app",
         "package": "org.videolan.vlc"}
    """

    if not isinstance(data, dict):
        emit("tv_remote_result", {
            "ok": False,
            "error": "Invalid command data"
        })
        return

    command = data.get("command")

    allowed_commands = {
        "up",
        "down",
        "left",
        "right",
        "select",
        "back",
        "home",
        "power",
        "vol_up",
        "vol_down",
        "mute",
        "youtube",
        "netflix",
        "status",
        "screenshot",
        "type_text",
        "launch_app",
    }

    if command not in allowed_commands:
        emit("tv_remote_result", {
            "ok": False,
            "command": command,
            "error": "Unsupported TV command"
        })
        return

    kwargs = {}

    if command == "type_text":
        kwargs["text"] = str(data.get("text", ""))

    elif command == "launch_app":
        package = str(data.get("package", "")).strip()

        if not package:
            emit("tv_remote_result", {
                "ok": False,
                "command": command,
                "error": "Application package is missing"
            })
            return

        # Basic validation. Package names are deliberately restricted
        # to the Android package-name character set.
        if not all(
            part.replace("_", "").isalnum()
            for part in package.split(".")
        ):
            emit("tv_remote_result", {
                "ok": False,
                "command": command,
                "error": "Invalid Android package name"
            })
            return

        kwargs["package"] = package

    elif command == "screenshot":
        filename = data.get("filename")

        if filename:
            kwargs["filename"] = str(filename)

    try:
        result = send_tv_command(command, **kwargs)

        emit("tv_remote_result", {
            **result,
            "command": command,
        })

    except TVRemoteError as exc:
        emit("tv_remote_result", {
            "ok": False,
            "command": command,
            "error": str(exc),
        })


# ------------------------------------------------------------
# Convenience Socket.IO events
# ------------------------------------------------------------
#
# These aren't strictly necessary because the generic
# tv_remote_command event handles everything. They make the
# browser-side JavaScript cleaner and give us a stable API
# if the UI is expanded later.
# ------------------------------------------------------------

def _simple_command(command):
    try:
        result = send_tv_command(command)

        emit("tv_remote_result", {
            **result,
            "command": command,
        })

    except TVRemoteError as exc:
        emit("tv_remote_result", {
            "ok": False,
            "command": command,
            "error": str(exc),
        })


@socketio.on("tv_up")
def tv_up():
    _simple_command("up")


@socketio.on("tv_down")
def tv_down():
    _simple_command("down")


@socketio.on("tv_left")
def tv_left():
    _simple_command("left")


@socketio.on("tv_right")
def tv_right():
    _simple_command("right")


@socketio.on("tv_select")
def tv_select():
    _simple_command("select")


@socketio.on("tv_back")
def tv_back():
    _simple_command("back")


@socketio.on("tv_home")
def tv_home():
    _simple_command("home")


@socketio.on("tv_power")
def tv_power():
    _simple_command("power")


@socketio.on("tv_vol_up")
def tv_vol_up():
    _simple_command("vol_up")


@socketio.on("tv_vol_down")
def tv_vol_down():
    _simple_command("vol_down")


@socketio.on("tv_mute")
def tv_mute():
    _simple_command("mute")


@socketio.on("tv_status")
def tv_status():
    _simple_command("status")
