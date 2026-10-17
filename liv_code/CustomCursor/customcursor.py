import pyautogui
import tkinter as tk

root = tk.Tk()
root.attributes("-topmost", True)
root.overrideredirect(True)

label = tk.Label(root, font=("Arial", 14), bg="black", fg="white")
label.pack()

def update():
    x, y = pyautogui.position()
    label.config(text=f"X: {x}  Y: {y}")
    root.geometry(f"+{x+15}+{y+15}")
    root.after(50, update)

update()
root.mainloop()
