# main_burlington.py

import random

from burlington_read_vocab import initWord, finalizeWord

def main():
    words = initWord()

    if not words:
        print("No data loaded.")
        return

    print("First 10 data points in the array (or fewer if file is shorter):")
    for i, item in enumerate(words[:10], start=1):
        print(f"{i}: {item}")

if __name__ == "__main__":
    main()
