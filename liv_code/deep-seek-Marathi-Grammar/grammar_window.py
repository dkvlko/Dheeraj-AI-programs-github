import tkinter as tk
import random
from tkinter import ttk
from pathlib import Path
from gemini_grammar_check import check_sentence

from burlington_read_vocab import initWord   # Import your function

TASKS = initWord()   # TASKS now becomes the returned array from file

# ------------------------------------------------------------
# Stub functions you can replace with your real logic
# ------------------------------------------------------------

#TASKS = [
#    "Write an interesting English sentence using the word: serendipity",
#    "Write an interesting English sentence using the word: inevitable",
#    "Write an interesting English sentence using the word: gratitude",
#]


class TaskProvider:
    """
    Simple provider of tasks.
    Now returns a random task instead of cycling sequentially.
    """
    def __init__(self):
        self.index = 0   # kept so rest of your code is untouched

    def get_task(self) -> str:
        if not TASKS:
            return "No task available."
        # Pick a random task instead of using self.index
        task = random.choice(TASKS)
        #return task
        return f"Write an interesting English sentence using the word: {task}"

task_provider = TaskProvider()


def getWord() -> str:
    """
    This function is called whenever a new task is needed.
    Currently, it cycles through the TASKS list.
    Replace with your own implementation if needed.
    """
    return task_provider.get_task()


def getResponse(user_text: str, task_text: str) -> str:
    """
    Called when 'Evaluate Grammar' is pressed.
    You can replace this with real grammar-check logic.
    For now, it just returns 'Success' as requested.
    """
    # TODO: Add your actual evaluation logic here
    user_text = check_sentence(user_text)
    return user_text 


# ------------------------------------------------------------
# GUI Application
# ------------------------------------------------------------

class GrammarApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Grammar Evaluation Panel")

        # Maximize window (Windows-friendly)
        try:
            self.state("zoomed")
        except tk.TclError:
            # Fallback if 'zoomed' is not supported
            self.attributes("-zoomed", True)

        self.current_task_text = ""

        # Make root resizable layout
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # Create scrollable canvas
        self._create_scrollable_area()

        # Build content inside scrollable frame
        self._build_ui()

        # Load the first task
        self.load_new_task()

    # ------------------ Scrollable layout ------------------ #
    def _create_scrollable_area(self):
        # Canvas + scrollbars
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.v_scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.h_scrollbar = ttk.Scrollbar(
            self, orient="horizontal", command=self.canvas.xview
        )

        self.canvas.configure(yscrollcommand=self.v_scrollbar.set,
                              xscrollcommand=self.h_scrollbar.set)

        # Grid them
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")

        # Frame inside the canvas which will hold everything
        self.content_frame = ttk.Frame(self.canvas)
        self.content_window = self.canvas.create_window(
            (0, 0), window=self.content_frame, anchor="nw"
        )

        # Update scrollregion whenever content_frame size changes
        self.content_frame.bind("<Configure>", self._on_frame_configure)

        # Optional: adjust inner frame width when canvas size changes
        # while still allowing horizontal scroll.
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_frame_configure(self, event):
        """Reset the scroll region to encompass the inner frame."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """
        Ensures the content frame is at least as wide as the canvas,
        so widgets can expand, but horizontal scroll still works.
        """
        canvas_width = event.width
        self.canvas.itemconfig(self.content_window, width=canvas_width)

    # ------------------ Build UI ------------------ #
    def _build_ui(self):
        # Configure rows in content frame: upper (1/3) and lower (2/3)
        self.content_frame.rowconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=2)
        self.content_frame.columnconfigure(0, weight=1)

        # Upper frame
        self.upper_frame = ttk.Frame(self.content_frame, padding=15)
        self.upper_frame.grid(row=0, column=0, sticky="nsew")
        self.upper_frame.columnconfigure(0, weight=1)

        # Lower frame
        self.lower_frame = ttk.Frame(self.content_frame, padding=15)
        self.lower_frame.grid(row=1, column=0, sticky="nsew")
        self.lower_frame.columnconfigure(0, weight=1)

        self._build_upper_frame()
        self._build_lower_frame()

    def _build_upper_frame(self):
        # Task label (centered text)
        self.task_label = ttk.Label(
            self.upper_frame,
            text="",
            anchor="center",
            justify="center",
            font=("Segoe UI", 14, "bold"),
            wraplength=1000,  # will adapt due to canvas width changes
        )
        self.task_label.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        # Text input field (multi-line)
        self.input_text = tk.Text(
            self.upper_frame,
            height=5,
            font=("Segoe UI", 12),
            wrap="word",
        )
        self.input_text.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.upper_frame.rowconfigure(1, weight=1)

        # Button row
        button_frame = ttk.Frame(self.upper_frame)
        button_frame.grid(row=2, column=0, pady=(5, 0), sticky="w")
        # Ensure some spacing between buttons
        for i in range(2):
            button_frame.columnconfigure(i, weight=0)

        # Evaluate Grammar button
        self.evaluate_button = ttk.Button(
            button_frame,
            text="Evaluate Grammar",
            command=self.on_evaluate,
        )
        self.evaluate_button.grid(row=0, column=0, padx=(0, 10))

        # Next button (initially inactive)
        self.next_button = ttk.Button(
            button_frame,
            text="Next",
            command=self.on_next,
        )
        self.next_button.grid(row=0, column=1)

        # Make Next inactive at start
        self.next_button.state(["disabled"])

    def _build_lower_frame(self):
        # Label for result area
        result_label = ttk.Label(
            self.lower_frame,
            text="Result:",
            font=("Segoe UI", 12, "bold"),
        )
        result_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        # Text widget for displaying response
        self.response_text = tk.Text(
            self.lower_frame,
            height=10,
            font=("Segoe UI", 12),
            wrap="word",
            state="disabled",
        )
        self.response_text.grid(row=1, column=0, sticky="nsew")
        self.lower_frame.rowconfigure(1, weight=1)

    # ------------------ Logic ------------------ #
    def load_new_task(self):
        """Fetches a new task via getWord() and updates the UI."""
        self.current_task_text = getWord()
        self.task_label.config(text=self.current_task_text)

        # Clear input area and response area
        self.input_text.delete("1.0", "end")
        self._set_response_text("")

        # Enable Evaluate, disable Next
        self.evaluate_button.state(["!disabled"])
        self.next_button.state(["disabled"])

    def _set_response_text(self, text: str):
        self.response_text.config(state="normal")
        self.response_text.delete("1.0", "end")
        if text:
            self.response_text.insert("1.0", text)
        self.response_text.config(state="disabled")

    def on_evaluate(self):
        """
        Called when Evaluate Grammar button is pressed.
        Calls getResponse() and updates the lower frame.
        """
        user_text = self.input_text.get("1.0", "end-1c")
        task_text = self.current_task_text

        response = getResponse(user_text, task_text)
        self._set_response_text(response)

        # After evaluation: disable Evaluate, enable Next
        self.evaluate_button.state(["disabled"])
        self.next_button.state(["!disabled"])

    def on_next(self):
        """
        Called when Next button is pressed.
        Loads a new task via getWord(), clears fields, and updates button states.
        """
        self.load_new_task()


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    app = GrammarApp()
    app.mainloop()
