# burlington_read_vocab.py
#Has two functions. 1.initWord() - Reads vocab file and returns it as array
#2.finalizeWord() takes two arrays and saves them as left and complete words

from pathlib import Path

def initWord():
    """
    Reads the vocabulary file and returns a list where
    each element is one line from the file.
    """
    vocab_file = Path(r"C:\Users\dheer\OneDrive\DheerajOnHP\liv_code\burlington_vocab_undone.txt")

    # Read all lines, strip trailing newlines
    try:
        with vocab_file.open("r", encoding="utf-8") as f:
            lines = [line.rstrip("\n") for line in f]
    except FileNotFoundError:
        print(f"Error: File not found: {vocab_file}")
        return []

    return lines


def finalizeWord(start_array: list[str], done_array: list[str]) -> None:
    """
    Save start_array and done_array as text files.
    Each element of the arrays is written on a new line.
    Existing files (if any) are deleted first.
    """

    # File paths kept *inside* the function now
    UNDONE_FILE = Path(r"C:\Users\dheer\OneDrive\DheerajOnHP\liv_code\burlington_vocab_undone.txt")
    DONE_FILE   = Path(r"C:\Users\dheer\OneDrive\DheerajOnHP\liv_code\burlington_vocab_done.txt")

    # Delete files if they already exist
    for path in (UNDONE_FILE, DONE_FILE):
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    # Write remaining (undone) words
    UNDONE_FILE.write_text("\n".join(start_array), encoding="utf-8")

    # Write completed (done) words
    DONE_FILE.write_text("\n".join(done_array), encoding="utf-8")