# main_grammar.py
from grammar_panel import initWindow


def main() -> None:
    # Make sure `word` exists and is non-empty
    word = "example"   # <-- change this as you like
    print(f"\nYour word: {word}")

    task = "Write an interesting English sentence using word : " + word

    # Open the UI window
    initWindow(task)


if __name__ == "__main__":
    main()
