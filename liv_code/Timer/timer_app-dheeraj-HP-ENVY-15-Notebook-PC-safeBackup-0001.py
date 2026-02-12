# modified_timer_app.py
# Based on the user's original file (repeat_timer_minimal_fixed2.py).
# Changes:
#  - Start button's functionality commented out (disabled) but original code left intact.
#  - Window/frame size reduced by 1.5 inches vertically (from bottom) and 2 inches horizontally
#    (1 inch left + 1 inch right) using winfo_fpixels('1i') for DPI-aware conversion.

import tkinter as tk
from tkinter import messagebox
import winsound

import base64, tempfile, os

# Your WAV encoded as base64 string (truncated here for example)
siren_144229_wav_b64 = b"""
UklGRlYnKwBXQVZFZm10IBAAAAAAAAAAQAAAAEAAAACAAAAAgA=
"""


class MinimalRepeatTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("Repeat Timer")

        # --- initial geometry (kept similar to original) ---
        # We'll set an initial geometry and then reduce it DPI-aware by the requested amounts.
        self.root.geometry("288x288")
        self.root.minsize(288, 288)
        self.root.attributes("-topmost", True)

        # Schedule a DPI-aware reduction of the window size (1.5" vertical, 2" horizontal)
        # Using after(0, ...) to run once the window metrics are available.
        # Schedule a DPI-aware reduction of the window size (1.5" vertical, 2" horizontal)
        self.root.after(0, lambda: self._reduce_window_by_inches(2.0, 1.5))

        # State
        self.seconds_left = 0
        self.original_seconds = 0
        self.running = False
        self.after_id = None
        self.tick_gen = 0

        # --- UI ---
        container = tk.Frame(root, padx=10, pady=10)
        container.pack(expand=True, fill="both")

        tk.Label(container, text="Time (mm:ss or minutes):").pack(pady=(0,6))
        self.time_var = tk.StringVar(value="2:00")
        self.time_entry = tk.Entry(container, textvariable=self.time_var, width=10, justify="center", font=("Segoe UI", 12))
        self.time_entry.pack()

        self.time_label = tk.Label(container, text="00:00", font=("Segoe UI", 28, "bold"))
        self.time_label.pack(pady=14)

        btns = tk.Frame(container)
        btns.pack(pady=6)

        # --- START BUTTON: comment out functionality ---
        # Original (kept as comment so you can restore easily):
        # self.start_btn = tk.Button(btns, text="Start", width=12, command=self.start_timer)
        # Disabled / commented-out behaviour: give button a no-op command so the start action does nothing.
        self.start_btn = tk.Button(btns, text="Start", width=12, command=lambda: None)
        # (Optional) visually indicate it's inactive by disabling it - but keeping it enabled
        # may be what you want; currently it is enabled but does nothing. If you prefer it disabled:
        # self.start_btn.config(state="disabled")
        self.start_btn.grid(row=0, column=0, padx=6, pady=6)

        self.ack_btn = tk.Button(btns, text="Acknowledge / Restart", width=18, command=self.ack_restart)
        self.ack_btn.grid(row=0, column=1, padx=6, pady=6)

        self.update_display(0)

        # Tip: If you previously bound Enter to start, comment it out to avoid double-fires.
        # root.bind("<Return>", lambda e: self.start_timer())

    # --- Helpers ---
    def _reduce_window_by_inches(self, horiz_inches: float, vert_inches: float):
        """
        Reduce the current window width by horiz_inches (total, e.g. 2.0 means 1" left + 1" right)
        and reduce height by vert_inches from the bottom (so total height decreases by vert_inches).
        Uses winfo_fpixels('1i') to compute pixels per inch (DPI-aware).
        """
        try:
            # ensure geometry info is available
            self.root.update_idletasks()
            # current size in pixels
            cur_w = self.root.winfo_width()
            cur_h = self.root.winfo_height()

            # pixels per inch (float)
            ppi = self.root.winfo_fpixels('1i')

            reduce_w = int(round(horiz_inches * ppi))
            reduce_h = int(round(vert_inches * ppi))

            new_w = max(100, cur_w - reduce_w)
            new_h = max(100, cur_h - reduce_h)

            # Apply new geometry and minimum size
            self.root.geometry(f"{new_w}x{new_h}")
            self.root.minsize(new_w, new_h)
        except Exception:
            # If anything goes wrong (very rare), just skip resizing silently.
            pass

    def parse_time_to_seconds(self, txt: str) -> int:
        txt = txt.strip()
        if ":" in txt:
            m, s = txt.split(":")
            m, s = int(m), int(s)
            if m < 0 or not (0 <= s < 60):
                raise ValueError
            return m * 60 + s
        minutes = float(txt)
        if minutes <= 0:
            raise ValueError
        return int(round(minutes * 60))

    def play_alarm(self):
        #winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_LOOP)
        # Decode to a temporary WAV file
        wav_bytes = base64.b64decode(siren_144229_wav_b64)
        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmpfile.write(wav_bytes)
        tmpfile.close()

        # Play it in loop
        winsound.PlaySound(tmpfile.name,
                       winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)


    def stop_alarm(self):
        winsound.PlaySound(None, winsound.SND_PURGE)

    def update_display(self, seconds):
        m, s = divmod(max(0, int(seconds)), 60)
        self.time_label.config(text=f"{m:02d}:{s:02d}")

    def _cancel_pending(self):
        if self.after_id:
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def _set_running_ui(self, is_running: bool):
        self.running = is_running
        # Disable Start while running to avoid accidental double-starts
        # Note: Start button is currently a no-op. This line still manipulates it so behavior remains consistent.
        self.start_btn.config(state=("disabled" if is_running else "normal"))

    # --- Core logic ---
    def start_timer(self):
        try:
            total = self.parse_time_to_seconds(self.time_var.get())
        except Exception:
            messagebox.showerror("Invalid time", "Enter minutes (e.g. 5) or mm:ss (e.g. 05:00).")
            return

        self.stop_alarm()
        self._cancel_pending()
        self.original_seconds = total
        self.seconds_left = total
        self.tick_gen += 1
        self._set_running_ui(True)
        self._schedule_tick(self.tick_gen)

    def ack_restart(self):
        self.stop_alarm()
        self._cancel_pending()
        try:
            total = self.parse_time_to_seconds(self.time_var.get())
        except Exception:
            total = self.original_seconds if self.original_seconds > 0 else 300

        self.original_seconds = total
        self.seconds_left = total
        self.tick_gen += 1
        self._set_running_ui(True)
        self._schedule_tick(self.tick_gen)

    def _schedule_tick(self, gen):
        # Update immediately so you see the set time
        self.update_display(self.seconds_left)

        def _tick():
            # Ignore stale or stopped chains
            if gen != self.tick_gen or not self.running:
                return
            if self.seconds_left <= 0:
                self._set_running_ui(False)
                self.after_id = None
                self.play_alarm()
                return
            self.seconds_left -= 1
            self.update_display(self.seconds_left)
            self.after_id = self.root.after(1000, _tick)

        # Schedule first tick after 1000 ms
        self.after_id = self.root.after(1000, _tick)


if __name__ == "__main__":
    root = tk.Tk()
    root.attributes("-topmost", True)   # 🔹 keeps the window always on top
    app = MinimalRepeatTimer(root)
    root.mainloop()
