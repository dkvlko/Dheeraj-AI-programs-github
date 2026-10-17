import random
import secrets
from pathlib import Path

from . import wordle_bp
from . import static
from flask import jsonify, render_template, request


# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------

MODULE_DIR = Path(__file__).resolve().parent
WORD_FILE = MODULE_DIR / "data" / "five-letter-words.txt"


# ----------------------------------------------------------------------
# Load words once when this module is imported
# ----------------------------------------------------------------------

def load_words():
    words = set()

    with WORD_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            word = line.strip().lower()

            if len(word) == 5 and word.isalpha():
                words.add(word)

    if not words:
        raise RuntimeError(
            f"No valid five-letter words found in {WORD_FILE}"
        )

    return words


VALID_WORDS = load_words()
ANSWER_WORDS = tuple(sorted(VALID_WORDS))


# ----------------------------------------------------------------------
# In-memory games
#
# game_id -> {
#     "answer": "xxxxx",
#     "guesses": [],
#     "game_over": False,
#     "won": False
# }
#
# This is deliberately server-side. The answer is never sent to the
# browser until the game is over.
# ----------------------------------------------------------------------

GAMES = {}


# ----------------------------------------------------------------------
# Game creation
# ----------------------------------------------------------------------

def create_game():
    game_id = secrets.token_urlsafe(32)

    GAMES[game_id] = {
        "answer": random.choice(ANSWER_WORDS),
        "guesses": [],
        "game_over": False,
        "won": False,
    }

    return game_id


# ----------------------------------------------------------------------
# Word evaluation
# ----------------------------------------------------------------------

def evaluate_guess(answer, guess):
    """
    Return a list containing:

        correct = correct letter, correct position
        present = correct letter, wrong position
        absent  = letter not available in the answer

    Uses the standard two-pass algorithm so repeated letters are handled
    correctly.
    """

    result = ["absent"] * 5

    # Remaining occurrences of letters after exact matches
    remaining = {}

    # Pass 1: exact matches
    for i in range(5):
        if guess[i] == answer[i]:
            result[i] = "correct"
        else:
            letter = answer[i]
            remaining[letter] = remaining.get(letter, 0) + 1

    # Pass 2: misplaced letters
    for i in range(5):
        if result[i] == "correct":
            continue

        letter = guess[i]

        if remaining.get(letter, 0) > 0:
            result[i] = "present"
            remaining[letter] -= 1

    return result


# ----------------------------------------------------------------------
# Front page
# ----------------------------------------------------------------------

@wordle_bp.route("/")
def index():
    return render_template("wordle/index.html")


# ----------------------------------------------------------------------
# Create a new game
# ----------------------------------------------------------------------

@wordle_bp.route("/api/new", methods=["POST"])
def new_game():
    game_id = create_game()

    return jsonify({
        "success": True,
        "game_id": game_id,
        "max_attempts": 6,
    })


# ----------------------------------------------------------------------
# Submit a guess
# ----------------------------------------------------------------------

@wordle_bp.route("/api/guess", methods=["POST"])
def guess():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "error": "Invalid request."
        }), 400

    game_id = data.get("game_id")
    guess_word = data.get("guess", "")

    if not game_id or game_id not in GAMES:
        return jsonify({
            "success": False,
            "error": "Game not found. Please start a new game."
        }), 400

    game = GAMES[game_id]

    # --------------------------------------------------------------
    # Game already finished
    # --------------------------------------------------------------

    if game["game_over"]:
        return jsonify({
            "success": False,
            "error": "This game is already over.",
            "game_over": True,
            "won": game["won"],
        }), 400

    # --------------------------------------------------------------
    # Normalise guess
    # --------------------------------------------------------------

    guess_word = str(guess_word).strip().lower()

    # --------------------------------------------------------------
    # Validate length
    # --------------------------------------------------------------

    if len(guess_word) != 5:
        return jsonify({
            "success": False,
            "error": "Word must contain exactly five letters."
        }), 400

    # --------------------------------------------------------------
    # Validate characters
    # --------------------------------------------------------------

    if not guess_word.isalpha():
        return jsonify({
            "success": False,
            "error": "Only letters are allowed."
        }), 400

    # --------------------------------------------------------------
    # Validate against word list
    # --------------------------------------------------------------

    if guess_word not in VALID_WORDS:
        return jsonify({
            "success": False,
            "error": "Not in word list."
        }), 400

    # --------------------------------------------------------------
    # Evaluate
    # --------------------------------------------------------------

    answer = game["answer"]

    result = evaluate_guess(answer, guess_word)

    game["guesses"].append(guess_word)

    attempt = len(game["guesses"])

    won = guess_word == answer
    game_over = won or attempt >= 6

    game["won"] = won
    game["game_over"] = game_over

    response = {
        "success": True,
        "guess": guess_word,
        "result": result,
        "attempt": attempt,
        "game_over": game_over,
        "won": won,
    }

    # Do NOT reveal the answer until the game has finished.
    if game_over:
        response["answer"] = answer

    return jsonify(response)
