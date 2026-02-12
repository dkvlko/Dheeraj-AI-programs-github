import ctypes
import time
import sys

# ================== CONFIGURABLE SETTINGS ==================

# Minutes of user inactivity (no keyboard/mouse) before screen turns off
IDLE_BEFORE_OFF_MINUTES = 30  # change as you like

# Minutes to keep the screen off (if still no input) before turning it on automatically
OFF_DURATION_MINUTES = 60     # change as you like

# Poll interval (seconds). Lower = more responsive but slightly more CPU usage.
POLL_INTERVAL_SECONDS = 2.0

# ==========================================================

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Constants from Win32 API
HWND_BROADCAST   = 0xFFFF
WM_SYSCOMMAND    = 0x0112
SC_MONITORPOWER  = 0xF170

# For fake mouse input
MOUSEEVENTF_MOVE = 0x0001

# LASTINPUTINFO structure for GetLastInputInfo
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("dwTime", ctypes.c_uint)
    ]

def get_idle_time_ms():
    """
    Returns the number of milliseconds since the last user input
    (keyboard or mouse), using GetLastInputInfo.
    """
    last_input_info = LASTINPUTINFO()
    last_input_info.cbSize = ctypes.sizeof(LASTINPUTINFO)

    if not user32.GetLastInputInfo(ctypes.byref(last_input_info)):
        raise ctypes.WinError()

    # GetTickCount is time since system started, in ms
    tick_count = kernel32.GetTickCount()
    idle_ms = tick_count - last_input_info.dwTime
    return idle_ms

def turn_monitor_off():
    """
    Tells Windows to turn off the monitor(s).
    """
    # lParam = 2 => power off display
    user32.SendMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)

def turn_monitor_on():
    """
    Tells Windows to turn on the monitor(s).
    """
    # lParam = -1 => turn on display
    user32.SendMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, -1)

def fake_user_input():
    """
    Send a tiny mouse move event to reset Windows idle timer.
    No visible cursor movement.
    """
    user32.mouse_event(MOUSEEVENTF_MOVE, 0, 0, 0, 0)

def main():
    idle_before_off_ms = IDLE_BEFORE_OFF_MINUTES * 60 * 1000
    off_duration_ms    = OFF_DURATION_MINUTES * 60 * 1000

    monitor_is_off = False
    off_start_tick = None          # GetTickCount() when we turned monitor off
    idle_at_off_ms = None          # idle time at the moment of turning off

    print(f"Idle-to-off: {IDLE_BEFORE_OFF_MINUTES} min, "
          f"Off-duration: {OFF_DURATION_MINUTES} min")

    try:
        while True:
            idle_ms = get_idle_time_ms()
            now_tick = kernel32.GetTickCount()

            if not monitor_is_off:
                # If user has been idle long enough, turn off monitor
                if idle_ms >= idle_before_off_ms:
                    print("[INFO] Idle threshold reached, turning monitor OFF")
                    turn_monitor_off()
                    monitor_is_off = True
                    off_start_tick = now_tick
                    idle_at_off_ms = idle_ms
            else:
                # Monitor is currently off
                # 1) Check if user activity happened since we turned it off
                if idle_ms < idle_at_off_ms:
                    # This means a new input occurred (idle time reset)
                    print("[INFO] User activity detected, turning monitor ON and resetting timers")
                    turn_monitor_on()
                    monitor_is_off = False
                    off_start_tick = None
                    idle_at_off_ms = None

                else:
                    # 2) If no new input, check if we've kept it off long enough
                    elapsed_off_ms = now_tick - off_start_tick
                    if elapsed_off_ms >= off_duration_ms:
                        print("[INFO] Automatic ON after off-duration elapsed")
                        turn_monitor_on()
                        # Fake a tiny input so that Windows' idle timer resets
                        fake_user_input()
                        monitor_is_off = False
                        off_start_tick = None
                        idle_at_off_ms = None

            time.sleep(POLL_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n[INFO] Exiting script.")
        sys.exit(0)

if __name__ == "__main__":
    main()
