from flask import render_template
from flask_socketio import SocketIO
from . import test_bp
from . import static
import pyautogui
import threading
import sys

# Your existing socketio object
from app import socketio

# Laptop screen dimensions
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()

dxo=0.0
dyo=0.0


# Protect PyAutoGUI/X11 operations from concurrent Socket.IO handlers
pyautogui_lock = threading.Lock()

SCROLL_SENSITIVITY = 1.0

def scroll_laptop_mouse(amount):
    with pyautogui_lock:
        pyautogui.scroll(amount * SCROLL_SENSITIVITY)
    sys.stdout.flush()

def click_laptop_mouse(button="left"):
    with pyautogui_lock:
        pyautogui.click(button=button)
    sys.stdout.flush()

def double_click_laptop_mouse(button="left"):
    with pyautogui_lock:
        pyautogui.doubleClick(button=button, interval=0.1)
    sys.stdout.flush()

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

@test_bp.route("/")
def mouse_test():
    return render_template("mouse_test.html")


@socketio.on("mouse_test_move")
def mouse_test_move(data):
    #global dxo, dyo
    dx = data.get("dx", 0)
    dy = data.get("dy", 0)


    with pyautogui_lock:

        #print("old x,y ",dxo,",",dyo,flush=True)
        #print("new x,y ",dx,",",dy,flush=True)
        #dxo = float(dx)
        #dyo = float(dy)
        move_laptop_cursor(dx, dy)

@socketio.on("mouse_test_click")
def mouse_test_click(data):
    button = data.get("button", "left")
    click_laptop_mouse(button)


@socketio.on("mouse_test_double_click")
def mouse_test_double_click():
    double_click_laptop_mouse()


@socketio.on("mouse_test_scroll")
def mouse_test_scroll(data):
    amount = float(data.get("amount", 0))
    scroll_laptop_mouse(amount)

@socketio.on("mouse_test_down")
def mouse_test_down(data):
    button = data.get("button", "left")

    print(f"MOUSE DOWN: {button}")


@socketio.on("mouse_test_up")
def mouse_test_up(data):
    button = data.get("button", "left")

    print(f"MOUSE UP: {button}")
