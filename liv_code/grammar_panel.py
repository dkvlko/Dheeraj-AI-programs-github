# grammar_panel.py
# creates the GUI check grammar APP

import tkinter as tk
from tkinter import ttk


def getResponse() -> str:
    """
    Stub function that simulates grammar evaluation.
    For now, it always returns 'Success'.
    """
    return "Success"


def initWindow(task: str) -> None:
    """
    Creates a full-size window with:
      - Upper frame (about 1/3 height):
          * centered task text
          * multi-line text input (font size 12, as wide as the window)
          * 'Evaluate Grammar' button
      - Lower frame (about 2/3 height):
          * displays the result from getResponse()
    Entire window is scrollable horizontally and vertically.
    """
    root = tk.Tk()
    root.title("Grammar Evaluation Panel")

    # Make the window full-size / maximized (Windows-friendly)
    try:
        root.state("zoomed")
    except tk.TclError:
        # Fallback: manually set to screen size
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        root.geometry(f"{screen_w}x{screen_h}")

    # ===== Scrollable canvas setup (both directions) =====
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)

    canvas = tk.Canvas(root)
    canvas.grid(row=0, column=0, sticky="nsew")

    v_scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    v_scrollbar.grid(row=0, column=1, sticky="ns")

    h_scrollbar = ttk.Scrollbar(root, orient="horizontal", command=canvas.xview)
    h_scrollbar.grid(row=1, column=0, sticky="ew")

    canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Frame *inside* the canvas that will hold all content
    scrollable_frame = ttk.Frame(canvas)
    scrollable_frame_id = canvas.create_window(
        (0, 0),
        window=scrollable_frame,
        anchor="nw"
    )

    # Update scroll region when size changes
    def on_frame_configure(_event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    scrollable_frame.bind("<Configure>", on_frame_configure)

    # Make canvas properly resize with the window
    def on_canvas_configure(event):
        # Make the inner frame at least as wide as the canvas
        canvas.itemconfig(scrollable_frame_id, width=event.width)

    canvas.bind("<Configure>", on_canvas_configure)

    # ===== Layout for top & bottom frames (1/3 : 2/3 split) =====
    scrollable_frame.rowconfigure(0, weight=1)  # upper frame ~1/3
    scrollable_frame.rowconfigure(1, weight=2)  # lower frame ~2/3
    scrollable_frame.columnconfigure(0, weight=1)

    top_frame = ttk.Frame(scrollable_frame, padding=20)
    bottom_frame = ttk.Frame(scrollable_frame, padding=20)

    top_frame.grid(row=0, column=0, sticky="nsew")
    bottom_frame.grid(row=1, column=0, sticky="nsew")

    # ===== Upper frame contents =====
    # Task label (centered)
    task_label = ttk.Label(
        top_frame,
        text=task,
        anchor="center",
        justify="center",
        font=("Segoe UI", 12)
    )
    task_label.pack(side="top", fill="x", pady=(0, 15))

    # Text input box for user sentence(s)
    input_text = tk.Text(
        top_frame,
        height=5,          # enough for a few sentences
        font=("Segoe UI", 12),
        wrap="word"
    )
    input_text.pack(side="top", fill="both", expand=True, pady=(0, 15))

    # Submit button
    # Will call getResponse() and show result in lower frame
    result_label = ttk.Label(
        bottom_frame,
        text="",
        anchor="nw",
        justify="left",
        font=("Segoe UI", 12)
    )
    result_label.pack(side="top", fill="both", expand=True)

    def on_evaluate():
        # You *could* grab user text here if needed:
        # user_text = input_text.get("1.0", tk.END).strip()
        response = getResponse()
        result_label.config(text=response)

    submit_button = ttk.Button(
        top_frame,
        text="Evaluate Grammar",
        command=on_evaluate
    )
    submit_button.pack(side="top", pady=(0, 10))

    root.mainloop()
