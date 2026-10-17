import pyautogui
import time

# Safety pause: move mouse to corner to abort
pyautogui.FAILSAFE = True

# Small delay before starting (gives you time to switch window)
time.sleep(3)

# Step 1: Move to (106, 227) and click
pyautogui.moveTo(106, 227, duration=0.3)
pyautogui.click()
time.sleep(5)

# Step 2: Move to (812, 437) and click
pyautogui.moveTo(812, 437, duration=0.3)
pyautogui.click()
time.sleep(1)

# Step 3: Type text
pyautogui.write("Which are top 10 International Headlines of the day(17 April 2026)?", interval=0.05)

# Step 4: Move to (1169, 437) and click
pyautogui.moveTo(1169, 437, duration=0.3)
pyautogui.click()
time.sleep(20)

# Step 5: Press Ctrl + S
pyautogui.hotkey('ctrl', 's')

#Step 6: Click Save As and wait 3 seconds
pyautogui.moveTo(1043, 240, duration=0.3)
pyautogui.click()
time.sleep(5)

