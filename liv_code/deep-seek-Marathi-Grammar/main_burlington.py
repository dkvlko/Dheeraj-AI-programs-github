# main_burlington.py
#Uses burlington_read_vocab.py file 
#gets the array from burlington_read_vocab.py
#picks a random word.
#if user wants then word is displayed or else array is saved back to the disk

import random

from burlington_read_vocab import initWord, finalizeWord

def main() -> None:
    # Get the list of words from your existing function.
    start_array = initWord()

    if not start_array:
        print("No words available in start_array. Exiting.")
        return

    done_array: list[str] = []

    while True:
        if not start_array:
            print("No more words left. You have gone through all words!")
            break

        # Pick a random word from start_array
        idx = random.randrange(len(start_array))
        word = start_array.pop(idx)   # remove from start_array
        done_array.append(word)       # add to done_array

        print(f"\nYour word: {word}")

        # Ask user if they want another word
        answer = input("Do you want to see a new word? (yes/no): ").strip().lower()

        # Basic input validation
        while answer not in ("y", "yes", "n", "no"):
            answer = input("Please type yes or no: ").strip().lower()

        if answer in ("n", "no"):
            break

    # Save both arrays to files
    finalizeWord(start_array, done_array)
    print("\nWords saved. Goodbye!")

if __name__ == "__main__":
    main()
