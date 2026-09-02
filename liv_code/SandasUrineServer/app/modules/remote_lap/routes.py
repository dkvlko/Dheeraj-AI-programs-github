from flask import render_template
from flask_socketio import emit
import pyautogui 
from . import remotelap_bp
from . import static
import threading
import math
pyautogui.FAILSAFE = False
#SCREEN_WIDTH = 1366
#SCREEN_HEIGHT = 768
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
cursor_x, cursor_y = pyautogui.position()
#print("Screen Size ",SCREEN_HEIGHT,",",SCREEN_WIDTH)
cursor_x = max(0, min(SCREEN_WIDTH - 1, cursor_x))
cursor_y = max(0, min(SCREEN_HEIGHT - 1, cursor_y))
#print("cursor ",cursor_x,",",cursor_y)
pyautogui_lock = threading.Lock()

@remotelap_bp.route("/")
def lapremote():
    return render_template("lapremote.html", page="remote")


@remotelap_bp.route("/lapmouse")
def lapmouse():
    return render_template("lapremote.html", page="mouse")

def register_socket_handlers(socketio):

    @socketio.on("mouse_move")
    def mouse_move(data):
        global cursor_x, cursor_y

        try:
            dx = float(data.get("dx", 0))
            dy = float(data.get("dy", 0))


            with pyautogui_lock:

                new_x = cursor_x + dx
                new_y = cursor_y + dy

                # ------------------------------------------------
                # Screen boundary
                # ------------------------------------------------

                new_x = max(
                    0,
                    min(SCREEN_WIDTH - 1, new_x)
                )

                new_y = max(
                    0,
                    min(SCREEN_HEIGHT - 1, new_y)
                )

                actual_dx = new_x - cursor_x
                actual_dy = new_y - cursor_y

                if actual_dx != 0 or actual_dy != 0:

                    pyautogui.moveRel(
                        actual_dx,
                        actual_dy,
                        duration=0
                    )

                cursor_x = math.floor(new_x)
                cursor_y = math.floor(new_y)
                
                #print("global new cursor ",cursor_x,",",cursor_y)

        except (TypeError, ValueError):
            pass


    @socketio.on("mouse_click")
    def mouse_click(data):

        button = data.get("button", "left")

        if button not in ("left", "right", "middle"):
            return

        with pyautogui_lock:
            pyautogui.click(button=button)


    @socketio.on("mouse_double_click")
    def mouse_double_click():

        with pyautogui_lock:
            pyautogui.doubleClick(
                button="left",
                interval=0.08
            )


    @socketio.on("scroll")
    def scroll(data):

        try:
            amount = float(data.get("amount", 0))

            amount = max(-20, min(20, amount))

            with pyautogui_lock:
                pyautogui.scroll(amount)

        except (TypeError, ValueError):
            pass
