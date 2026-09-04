from flask import render_template
from flask_socketio import emit
import pyautogui 
from . import remotelap_bp
from . import static
import threading
import math
import sys
from app import socketio

SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
pyautogui_lock = threading.Lock()
SCROLL_SENSITIVITY = 1.0 


def scroll_laptop_mouse(amount):
        pyautogui.scroll(amount * SCROLL_SENSITIVITY)

def click_laptop_mouse(button="left"):
        pyautogui.click(button=button)

def double_click_laptop_mouse(button="left"):
        pyautogui.doubleClick(button=button, interval=0.1)

def move_laptop_cursor(dx, dy):
    """
    Move the laptop cursor relatively by dx, dy.

    The movement is constrained to the actual laptop screen size.
    """
    
    # Current actual cursor position
    current_x, current_y = pyautogui.position()

    # Calculate desired new position
    new_x = current_x + dx
    new_y = current_y + dy

    # Keep cursor inside the screen
    new_x = max(0, min(SCREEN_WIDTH - 1, new_x))
    new_y = max(0, min(SCREEN_HEIGHT - 1, new_y))

    # Calculate actual movement after boundary clipping
    actual_dx = new_x - current_x
    actual_dy = new_y - current_y

    # Move only if there is actual movement
    #if actual_dx != 0 or actual_dy != 0:
    pyautogui.moveRel(
        actual_dx,
        actual_dy,
        duration=0
    )

    sys.stdout.flush()
    return

@remotelap_bp.route("/")
def lapremote():
    return render_template("lapremote.html", page="remote")


@remotelap_bp.route("/lapmouse")
def lapmouse():
    return render_template("lapremote.html", page="mouse")

#def register_socket_handlers(socketio):

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

@socketio.on("scroll")
def scroll(data):
    amount = float(data.get("amount", 0))
    scroll_laptop_mouse(amount)
