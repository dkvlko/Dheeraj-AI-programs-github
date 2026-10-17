import subprocess
import tempfile
import os
import time

def clean_latex(text):

    # remove filename prefix if present
    if ":" in text:
        text = text.split(":",1)[1]

    # remove OCR spacing commands
    text = text.replace("\\,", "")

    return text.strip()

def countdown(seconds):
    """
    Displays a countdown in the console before screenshot capture.
    """
    print(f"Screenshot will start in {seconds} seconds...")
    for i in range(seconds, 0, -1):
        print(f"{i}...", flush=True)
        time.sleep(1)


def take_screenshot():
    """
    Allows user to select a rectangular region of the screen.
    The screenshot is saved to a temporary file.
    """
    temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    temp_path = temp_file.name
    temp_file.close()

    subprocess.run([
        "gnome-screenshot",
        "-a",
        "-f", temp_path
    ])

    return temp_path


def run_pix2tex(image_path):
    """
    Runs pix2tex on the screenshot image
    and returns the LaTeX result.
    """
    result = subprocess.run(
        ["pix2tex", image_path],
        capture_output=True,
        text=True
    )

    return result.stdout.strip()


def main():

    countdown(7)

    print("Select the area containing the formula...")

    image_path = take_screenshot()

    print("Processing with pix2tex...")

    #latex = run_pix2tex(image_path)
    latex = clean_latex(run_pix2tex(image_path))
    latex = latex.replace("\\,", "")

    formatted = f"[latex]${latex}$[/latex]"

    print("\nDetected LaTeX:")
    print("----------------------")
    print(formatted)
    print("----------------------")

    os.remove(image_path)


if __name__ == "__main__":
    main()