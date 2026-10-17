import os
import subprocess
import time
from PIL import Image, ImageChops
from mss import mss
from pynput import keyboard

# Global list to store frames
frames = []

def send_notification(message):
    try:
        subprocess.run(["notify-send", "SuperScreenshot", message])
    except Exception:
        pass

def take_snapshot():
    # Small delay to ensure the OS has processed the key-press
    time.sleep(0.1)
    
    with mss() as sct:
        try:
            screenshot = sct.grab(sct.monitors[1])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            frames.append(img.convert("RGBA"))
            
            send_notification(f"Frame {len(frames)} captured!")
            print(f"Captured frame {len(frames)}")
        except Exception as e:
            print(f"Capture failed: {e}")
            send_notification("Capture failed! Check terminal.")

def save_and_exit():
    if not frames:
        send_notification("No frames captured. Exiting.")
        os._exit(0)

    print(f"Blending {len(frames)} frames...")
    base = frames[0]
    for i in range(1, len(frames)):
        base = ImageChops.lighter(base, frames[i])
    
    # Using a timestamp so you don't overwrite your work
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_file = f"superposition_{timestamp}.png"
    
    base.convert("RGB").save(output_file)
    send_notification(f"Saved to {output_file}")
    print(f"Done! Saved as {output_file}")
    os._exit(0)

# --- Initialization ---
print("--- Background Superposition Tool ---")

# Warm-up: Take a throwaway screenshot to initialize the display buffer
with mss() as sct:
    sct.grab(sct.monitors[1])
    print("Screen buffer initialized.")

# Hotkey Listener
with keyboard.GlobalHotKeys({
        '<ctrl>+<alt>+s': take_snapshot,
        '<ctrl>+<alt>+e': save_and_exit}) as h:
    
    print("Ready! Minimize this terminal and use:")
    print("  Ctrl+Alt+S  -> Snap")
    print("  Ctrl+Alt+E  -> Save & Exit")
    
    send_notification("Tool Ready - Buffer Initialized")
    h.join()