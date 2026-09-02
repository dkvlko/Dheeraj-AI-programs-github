from flask import Blueprint, render_template
from flask_socketio import emit
import pyautogui

@remote_mouse_bp.route("/lapmouse")
def lapmouse():
    return render_template("lapremote.html", page="mouse")


def register_socket_handlers(socketio):

    @socketio.on("mouse_move")
    def mouse_move(data):
        try:
            dx = float(data.get("dx", 0))
            dy = float(data.get("dy", 0))

            # Ignore absurd values caused by a bad/disconnected client.
            dx = max(-100, min(100, dx))
            dy = max(-100, min(100, dy))

            pyautogui.moveRel(
                dx,
                dy,
                duration=0
            )

        except (TypeError, ValueError):
            pass

    @socketio.on("mouse_click")
    def mouse_click(data):
        button = data.get("button", "left")

        if button not in ("left", "right", "middle"):
            return

        pyautogui.click(button=button)

    @socketio.on("mouse_double_click")
    def mouse_double_click():
        pyautogui.doubleClick(button="left", interval=0.08)

    @socketio.on("mouse_down")
    def mouse_down(data):
        button = data.get("button", "left")

        if button in ("left", "right", "middle"):
            pyautogui.mouseDown(button=button)

    @socketio.on("mouse_up")
    def mouse_up(data):
        button = data.get("button", "left")

        if button in ("left", "right", "middle"):
            pyautogui.mouseUp(button=button)

    @socketio.on("scroll")
    def scroll(data):
        try:
            amount = float(data.get("amount", 0))
            amount = max(-20, min(20, amount))

            pyautogui.scroll(amount)

        except (TypeError, ValueError):
            pass
