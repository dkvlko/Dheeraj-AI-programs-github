from flask import render_template
from flask_socketio import emit
from . import tvremote_bp
from app import socketio

import json
import socket
import subprocess
import threading
import time

# The Android-TV connection daemon owns Remote v2, discovery and reconnect logic.
# Flask only talks to its Unix-domain command socket.
TV_REMOTE_SOCKET = "/run/tvandroidremote/remote.sock"
TV_REMOTE_SERVICE = "tvandroidremote.service"

# Prevent multiple browser requests from simultaneously trying to restart
# the same daemon.  A short cooldown also prevents a dead service from
# being restarted for every button press.
_restart_lock = threading.Lock()
_last_restart_time = 0.0
RESTART_COOLDOWN = 10
RESTART_WAIT = 2


class TVRemoteError(RuntimeError):
    pass


def _restart_tv_remote_service():
    """
    Restart the Android TV Remote v2 systemd service.

    This is only attempted when the Unix command socket is unavailable.
    A cooldown prevents repeated browser commands from causing a restart
    storm.
    """
    global _last_restart_time

    with _restart_lock:
        now = time.monotonic()

        if now - _last_restart_time < RESTART_COOLDOWN:
            return False, "restart cooldown active"

        _last_restart_time = now

        try:
            result = subprocess.run(
                ["sudo", "-n", "systemctl", "restart", TV_REMOTE_SERVICE],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=False,
            )

            if result.returncode != 0:
                error = result.stderr.strip() or (
                    f"systemctl exited with code {result.returncode}"
                )
                return False, error

            return True, "service restart requested"

        except subprocess.TimeoutExpired:
            return False, "systemctl restart timed out"

        except OSError as exc:
            return False, f"could not run systemctl: {exc}"


def _send_tv_command_once(command, **kwargs):
    """Send one command attempt to the daemon socket."""
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

        response = json.loads(response_data.decode("utf-8"))

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
            "Android TV remote service unavailable: " + str(exc)
        ) from exc

    except json.JSONDecodeError as exc:
        raise TVRemoteError(
            "Invalid response from Android TV remote service"
        ) from exc

    finally:
        sock.close()


def send_tv_command(command, **kwargs):
    """
    Send a JSON command to the Android TV Remote v2 daemon.

    If the Unix command socket is unavailable, request one systemd restart
    and retry the command once after the service has had time to start.
    """
    try:
        return _send_tv_command_once(command, **kwargs)

    except TVRemoteError as first_error:
        # Only restart when the daemon itself is unavailable.  Do not restart
        # it merely because the TV rejected an otherwise valid command.
        error_text = str(first_error).lower()
        service_unavailable = (
            "remote service unavailable" in error_text
            or "no response from android tv remote service" in error_text
            or "remote service timed out" in error_text
        )

        if not service_unavailable:
            raise

        restarted, restart_message = _restart_tv_remote_service()

        if not restarted:
            raise TVRemoteError(
                f"{first_error}; could not restart "
                f"{TV_REMOTE_SERVICE}: {restart_message}"
            ) from first_error

        time.sleep(RESTART_WAIT)

        try:
            return _send_tv_command_once(command, **kwargs)
        except TVRemoteError as second_error:
            raise TVRemoteError(
                f"{first_error}; {TV_REMOTE_SERVICE} was restarted "
                f"but the command is still unavailable: {second_error}"
            ) from second_error


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
        "wakeup",
        "vol_up",
        "vol_down",
        "mute",
        "youtube",
        "primevideo",
        "jiohotstar",
        "status",
        "screenshot",
        "type_text",
        "launch_app",
        "get_connection",
    }
    print("command sent: ",command)

    if command not in allowed_commands:
        emit("tv_remote_result", {
            "ok": False,
            "command": command,
            "error": "Unsupported TV command"
        })
        return

    # "get_connection" is a control-plane action.  It does not go
    # through the daemon socket because the purpose of the button is to
    # restart the daemon itself.
    if command == "get_connection":
        restarted, message = _restart_tv_remote_service()

        if restarted:
            emit("tv_remote_result", {
                "ok": True,
                "command": command,
                "output": "TV remote service restarted",
            })
        else:
            emit("tv_remote_result", {
                "ok": False,
                "command": command,
                "error": (
                    "Could not restart tvandroidremote.service: "
                    + message
                ),
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
                "error": "Application package or deep link is missing"
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
    print("Simple command: ",command)
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
