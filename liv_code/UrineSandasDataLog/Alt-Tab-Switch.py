import os
import re
import time
import pyautogui

# 1. ENVIRONMENT SETUP
username = "dkvlko"
os.environ["DISPLAY"] = ":1"
os.environ["XAUTHORITY"] = f"/home/{username}/.Xauthority"

def execute_window_switch(command_text):
    """
    Parses string like 'CW:Alt+nTAB' and executes the key sequence.
    """
    # Regex explains: Look for 'CW:Alt+', capture digits (\d+), then 'TAB'
    match = re.search(r"CW:Alt\+(\d+)TAB", command_text)
    
    if match:
        # Extract the number 'n'
        n = int(match.group(1))
        print(f"Command detected! Switching {n} windows...")
        
        try:
            # Hold Alt throughout the entire sequence
            with pyautogui.hold('alt'):
                for i in range(n):
                    pyautogui.press('tab')
                    print(f"  Pulse {i+1} of {n}")
                    
                    # 1 second delay as requested
                    time.sleep(1) 
                    
            print("Sequence complete. Alt released.")
            
        except Exception as e:
            print(f"Error executing keys: {e}")
    else:
        print(f"Text '{command_text}' did not match CW format. Ignoring.")

# --- EXAMPLE USAGE ---
if __name__ == "__main__":
    # Simulate receiving data from your websocket
    incoming_data = "CW:Alt+6TAB" 
    execute_window_switch(incoming_data)
