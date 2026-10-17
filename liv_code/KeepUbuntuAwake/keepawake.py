import pyautogui
import subprocess
import time

SCREEN_WIDTH = 1366
SCREEN_HEIGHT = 768

while True:
    # Current mouse position
    x, y = pyautogui.position()

    # Move 200 pixels to the right
    new_x = x + 200

    # If we reach the right edge, wrap around to the left
    if new_x >= SCREEN_WIDTH:
        new_x = new_x - SCREEN_WIDTH

    pyautogui.moveTo(new_x, y, duration=0.2)

    # Turn CAPS LOCK ON
    subprocess.run(["xdotool", "key", "Caps_Lock"])

    # Wait 2 seconds
    time.sleep(2)

    # Turn CAPS LOCK OFF
    subprocess.run(["xdotool", "key", "Caps_Lock"])
