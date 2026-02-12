import tkinter as tk
from tkinter import font

def show_table():
    value = entry.get().strip()
    output_text.delete("1.0", tk.END)

    if not value.isdigit():
        output_text.insert(tk.END, "Please enter a valid number.")
        return

    num = int(value)
    table = ""
    for i in range(1, 11):
        table += f"{num:3}  ×  {i:2}  =  {num * i}\n"

    output_text.insert(tk.END, table)


# Main window
root = tk.Tk()
root.title("Multiplication Table")
root.attributes("-fullscreen", True)   # Full screen mode

# Screen size (for clarity, though fullscreen is already applied)
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

# Fonts
input_font = font.Font(family="Times New Roman", size=16)
table_font = font.Font(family="Times New Roman", size=14)

# Frames
upper_frame = tk.Frame(root, height=screen_height // 5, bg="#dddddd")
lower_frame = tk.Frame(root, height=(screen_height * 4) // 5, bg="white")

upper_frame.pack(fill="x")
lower_frame.pack(fill="both", expand=True)

# ----- Upper Frame Content -----
label = tk.Label(
    upper_frame,
    text="Enter a number:",
    font=input_font,
    bg="#dddddd"
)
label.pack(pady=20)

entry = tk.Entry(
    upper_frame,
    font=input_font,
    width=10,
    justify="center"
)
entry.pack()

go_button = tk.Button(
    upper_frame,
    text="Go",
    font=input_font,
    width=8,
    command=show_table
)
go_button.pack(pady=10)

# ----- Lower Frame Content -----
output_text = tk.Text(
    lower_frame,
    font=table_font,
    wrap="none",
    padx=20,
    pady=20
)
output_text.pack(fill="both", expand=True)

# Exit on ESC key
root.bind("<Escape>", lambda e: root.destroy())

root.mainloop()
