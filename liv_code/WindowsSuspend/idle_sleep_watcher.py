"""
idle_sleep_watcher.py

Polls Windows input idle time every 2 seconds. If no keyboard/mouse input
for INACTIVITY_SECONDS (default 15 minutes = 900s) the script requests system
suspend (sleep). The script continues running across sleep/wake cycles and
resets its idle baseline after wake to avoid immediate re-sleep.

Notes:
 - You may need to run as Administrator if SetSuspendState fails due to policy.
 - Sleep vs Hibernate behavior depends on system power settings.
"""

import ctypes
import time
import logging
import sys
import subprocess

# ---------- Configuration ----------
POLL_INTERVAL_SECONDS = 2.0
INACTIVITY_SECONDS = 5 * 60  # 5 minutes
POST_WAKE_PAUSE_SECONDS = 5   # short pause after wake before resuming checks

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# ---------- WinAPI setup ----------
class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
try:
    powrprof = ctypes.windll.powrprof
    can_call_powrprof = True
except Exception:
    powrprof = None
    can_call_powrprof = False

GetLastInputInfo = user32.GetLastInputInfo
GetTickCount64 = getattr(kernel32, "GetTickCount64", None)

# ---------- Baseline / state ----------
last_reset_tick = None  # milliseconds tick baseline we can bump after wake

# ---------- Helper functions ----------
def get_current_tick_ms() -> int:
    """Return current system tick count in milliseconds (uses GetTickCount64 when available)."""
    if GetTickCount64 is not None:
        return int(GetTickCount64())
    return int(kernel32.GetTickCount())

def get_idle_seconds() -> float:
    """
    Returns number of seconds since last user input (mouse/keyboard),
    but respects last_reset_tick so we can ignore long idle accumulated during sleep.
    """
    global last_reset_tick
    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not GetLastInputInfo(ctypes.byref(li)):
        raise ctypes.WinError()

    now_ms = get_current_tick_ms()
    last_input_ms = int(li.dwTime)  # dwTime is ms tick count of last input

    # If we have a manual reset baseline that is newer than the last input,
    # treat that baseline as the "last activity" (avoids counting sleep time).
    if last_reset_tick is not None and last_reset_tick > last_input_ms:
        last_input_ms = last_reset_tick

    idle_ms = now_ms - last_input_ms
    if idle_ms < 0:
        idle_ms = 0
    return idle_ms / 1000.0

def try_sleep_windows() -> bool:
    """
    Attempt to put the system to sleep/standby.
    Returns True if call likely succeeded (non-zero from API or no exception in fallback).
    """
    logging.info("Requesting system sleep/standby...")
    if can_call_powrprof and powrprof is not None:
        try:
            # SetSuspendState(Hibernate=False, ForceCritical=False, DisableWakeEvent=False)
            res = powrprof.SetSuspendState(ctypes.c_bool(False), ctypes.c_bool(False), ctypes.c_bool(False))
            success = bool(res)
            logging.info(f"powrprof.SetSuspendState returned: {res} -> success={success}")
            return success
        except Exception as e:
            logging.exception("powrprof.SetSuspendState call failed: %s", e)

    # Fallback to rundll32 (may behave differently depending on system settings)
    try:
        logging.info("Trying fallback rundll32 approach...")
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,0,0"], shell=False, check=False)
        return True
    except Exception as e:
        logging.exception("rundll32 fallback failed: %s", e)
    return False

# ---------- Main loop ----------
def main_loop():
    global last_reset_tick
    logging.info("Idle Sleep Watcher started. Poll interval: %.1fs, inactivity threshold: %ds",
                 POLL_INTERVAL_SECONDS, INACTIVITY_SECONDS)

    # Initialize baseline to now so previous system uptime doesn't count as idle
    last_reset_tick = get_current_tick_ms()

    try:
        while True:
            idle = get_idle_seconds()
            logging.debug("Idle seconds: %.1f", idle)
            if idle >= INACTIVITY_SECONDS:
                logging.info("System idle for %.1f seconds (>= %d). Preparing to sleep...", idle, INACTIVITY_SECONDS)
                success = try_sleep_windows()
                if not success:
                    logging.warning("Request to sleep may have failed. Try running as Administrator or check power settings.")
                # On return from the blocking SetSuspendState call (i.e., after wake),
                # reset baseline so the long idle measured during sleep isn't counted.
                last_reset_tick = get_current_tick_ms()
                # small pause to avoid immediate re-trigger or busy loop after wake
                time.sleep(POST_WAKE_PAUSE_SECONDS)
                logging.info("Resuming idle monitoring after sleep/wake (baseline reset).")
            else:
                time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logging.info("Interrupted by user; exiting.")
    except Exception:
        logging.exception("Unhandled exception in main loop; exiting.")

if __name__ == "__main__":
    main_loop()
