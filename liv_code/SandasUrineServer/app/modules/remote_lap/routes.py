from flask import render_template
from flask_socketio import emit
#import pyautogui 
from . import remotelap_bp
from . import static
import threading
import math
import sys
import subprocess

# False -> next Zoom sends Super+W
# True  -> next Zoom sends Super+Z
zoom_state = False
from app import socketio


def get_screen_size():
    result = subprocess.run(
        ["xdotool", "getdisplaygeometry"],
        capture_output=True,
        text=True,
        check=True
    )

    return map(int, result.stdout.split())

SCREEN_WIDTH, SCREEN_HEIGHT = get_screen_size()
pyautogui_lock = threading.Lock()
SCROLL_SENSITIVITY = 1.0 


def scroll_laptop_mouse(amount):
    """
    Scroll the mouse wheel using xdotool.
    Positive amount = scroll up
    Negative amount = scroll down
    """

    clicks = abs(int(amount * SCROLL_SENSITIVITY))

    if clicks == 0:
        return

    # xdotool button 4 = scroll up
    # xdotool button 5 = scroll down
    button = "4" if amount > 0 else "5"

    subprocess.run(
        ["xdotool", "click", "--repeat", str(clicks), button],
        check=False
    )


def click_laptop_mouse(button="left"):
    """
    Perform a single mouse click using xdotool.
    """

    button_map = {
        "left": "1",
        "middle": "2",
        "right": "3"
    }

    xdotool_button = button_map.get(button, "1")

    subprocess.run(
        ["xdotool", "click", xdotool_button],
        check=False
    )


def double_click_laptop_mouse(button="left"):
    """
    Perform a double mouse click using xdotool.
    """

    button_map = {
        "left": "1",
        "middle": "2",
        "right": "3"
    }

    xdotool_button = button_map.get(button, "1")

    subprocess.run(
        [
            "xdotool",
            "click",
            "--repeat", "2",
            "--delay", "100",
            xdotool_button
        ],
        check=False
    )


def move_laptop_cursor(dx, dy):
    """
    Move the laptop cursor relatively by dx, dy using xdotool.
    Movement is constrained to the actual screen boundaries.
    """

    # Get current cursor position
    result = subprocess.run(
        ["xdotool", "getmouselocation", "--shell"],
        capture_output=True,
        text=True,
        check=False
    )

    # Parse X and Y from xdotool output
    x = y = None

    for line in result.stdout.splitlines():
        if line.startswith("X="):
            x = int(line[2:])
        elif line.startswith("Y="):
            y = int(line[2:])

    # If cursor position could not be obtained, do nothing
    if x is None or y is None:
        return

    # Calculate desired position
    new_x = x + int(dx)
    new_y = y + int(dy)

    # Boundary check
    new_x = max(0, min(SCREEN_WIDTH - 1, new_x))
    new_y = max(0, min(SCREEN_HEIGHT - 1, new_y))

    # Calculate actual movement after clipping
    actual_dx = new_x - x
    actual_dy = new_y - y

    # Move only if there is actual movement
    if actual_dx != 0 or actual_dy != 0:
        subprocess.run(
            [
                "xdotool",
                "mousemove_relative",
                "--",
                str(actual_dx),
                str(actual_dy)
            ],
            check=False
        )

@remotelap_bp.route("/")
def lapremote():
    return render_template("index.html")


@remotelap_bp.route("/mousepad")
def lapmouse():
    return render_template("mousepad.html")


@remotelap_bp.route("/keyboard")
def keyboard():
    return render_template("keyboard.html")
#def register_socket_handlers(socketio):

def send_key(key):
    """
    Send a key/key combination to the
    currently focused X11 window.
    """
    subprocess.run(
        ["xdotool", "key", key],
        check=False
    )


KEY_MAP = {
    "PrintScreen": "Print",
    "Enter": "Return",

    "grave": "grave",
    "minus": "minus",
    "equal": "equal",

    "leftBracket": "bracketleft",
    "rightBracket": "bracketright",

    "ShiftLeft": "Shift_L",
    "ShiftRight": "Shift_R",

    "ControlLeft": "Control_L",
    "ControlRight": "Control_R",
    "AltLeft": "Alt_L",
    "AltRight": "Alt_R",
    "SuperLeft": "Super_L",

    "ArrowLeft": "Left",
    "ArrowUp": "Up",
    "ArrowDown": "Down",
    "ArrowRight": "Right",

    "Space": "space",
}

@socketio.on("keyboard_key")
def handle_keyboard_key(data):
    global zoom_state
    key = data.get("key")

    if key in KEY_MAP:
        send_key(KEY_MAP[key])

    elif key in {
        "F1", "F2", "F3", "F4", "F5", "F6",
        "F7","F8", "F9", "F10", "F11", "F12"
    }:
        if key == "F8" :
            if not zoom_state :
                send_key("ctrl+z")
                zoom_state =True
            else :
                send_key("ctrl+w")
                zoom_state = False
        else :
            send_key(key)

    #elif key and len(key) == 1:
    elif key : 
        send_key(key)
    else:
        print("Keyboard: unknown key:", key)


@socketio.on("mouse_move")
def mouse_move(data):
    dx = data.get("dx", 0)
    dy = data.get("dy", 0)
    with pyautogui_lock:
        move_laptop_cursor(dx, dy)


@socketio.on("mouse_click")
def mouse_click(data):
    button = data.get("button", "left")
    click_laptop_mouse("left")


@socketio.on("mouse_click_right")
def mouse_click_right(data):
    button = data.get("button", "left")
    click_laptop_mouse("right")

@socketio.on("mouse_double_click")
def mouse_double_click():
    double_click_laptop_mouse()

@socketio.on("mouse_scroll")
def scroll(data):
    amount = float(data.get("amount", 0))
    scroll_laptop_mouse(amount)
