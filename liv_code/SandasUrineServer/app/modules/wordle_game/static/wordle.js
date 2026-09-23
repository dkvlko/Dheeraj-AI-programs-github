"use strict";


/* ================================================================
   GAME STATE
   ================================================================ */

let gameId = null;

let currentRow = 0;
let currentCol = 0;

let board = [
    ["", "", "", "", ""],
    ["", "", "", "", ""],
    ["", "", "", "", ""],
    ["", "", "", "", ""],
    ["", "", "", "", ""],
    ["", "", "", "", ""]
];

let gameOver = false;


/* ================================================================
   DOM ELEMENTS
   ================================================================ */

const messageArea = document.getElementById("message-area");
const attemptCounter = document.getElementById("attempt-counter");

const overlay = document.getElementById("game-overlay");
const resultSymbol = document.getElementById("result-symbol");
const resultTitle = document.getElementById("result-title");
const resultText = document.getElementById("result-text");
const answerDisplay = document.getElementById("answer-display");

const newGameButton = document.getElementById("new-game-button");
const playAgainButton = document.getElementById("play-again-button");

const keys = document.querySelectorAll(".key");


/* ================================================================
   START
   ================================================================ */

document.addEventListener("DOMContentLoaded", () => {

    initialiseKeyboard();
    initialiseKeyboardLayout();
    initialisePhysicalKeyboard();

    newGameButton.addEventListener("click", startNewGame);

    playAgainButton.addEventListener("click", startNewGame);

    startNewGame();
});


/* ================================================================
   NEW GAME
   ================================================================ */

async function startNewGame() {

    try {

        const response = await fetch(
            "/wordle/api/new",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                }
            }
        );

        if (!response.ok) {
            throw new Error("Unable to create game.");
        }

        const data = await response.json();

        gameId = data.game_id;

        currentRow = 0;
        currentCol = 0;

        gameOver = false;

        board = [
            ["", "", "", "", ""],
            ["", "", "", "", ""],
            ["", "", "", "", ""],
            ["", "", "", "", ""],
            ["", "", "", "", ""],
            ["", "", "", "", ""]
        ];

        clearBoard();

        resetKeyboard();

        hideOverlay();

        updateAttemptCounter();

        clearMessage();

    } catch (error) {

        console.error(error);

        showMessage("Unable to start game.");

    }
}


/* ================================================================
   BOARD
   ================================================================ */

function clearBoard() {

    document
        .querySelectorAll(".tile")
        .forEach(tile => {

            tile.textContent = "";

            tile.className = "tile";
        });
}


function getTile(row, col) {

    return document.querySelector(
        `.row[data-row="${row}"] .tile[data-col="${col}"]`
    );
}


function updateTile(row, col) {

    const tile = getTile(row, col);

    if (!tile) {
        return;
    }

    tile.textContent = board[row][col].toUpperCase();

    if (board[row][col] !== "") {

        tile.classList.add("filled");

        tile.classList.remove("pop");

        // Force reflow so repeated typing can animate.
        void tile.offsetWidth;

        tile.classList.add("pop");
    } else {

        tile.classList.remove("filled");
        tile.classList.remove("pop");
    }
}


/* ================================================================
   LETTER INPUT
   ================================================================ */

function enterLetter(letter) {

    if (gameOver) {
        return;
    }

    if (currentRow >= 6) {
        return;
    }

    if (currentCol >= 5) {
        return;
    }

    letter = letter.toLowerCase();

    if (!/^[a-z]$/.test(letter)) {
        return;
    }

    board[currentRow][currentCol] = letter;

    updateTile(currentRow, currentCol);

    currentCol++;
}


/* ================================================================
   BACKSPACE
   ================================================================ */

function deleteLetter() {

    if (gameOver) {
        return;
    }

    if (currentCol <= 0) {
        return;
    }

    currentCol--;

    board[currentRow][currentCol] = "";

    updateTile(currentRow, currentCol);
}


/* ================================================================
   ENTER
   ================================================================ */

async function submitGuess() {

    if (gameOver) {
        return;
    }

    if (currentCol !== 5) {

        showMessage("Not enough letters.");

        return;
    }

    const guess = board[currentRow].join("");

    clearMessage();

    try {

        const response = await fetch(
            "/wordle/api/guess",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    game_id: gameId,
                    guess: guess
                })
            }
        );

        const data = await response.json();

        if (!response.ok || !data.success) {

            showMessage(
                data.error || "Invalid guess."
            );

            return;
        }

        applyResult(
            currentRow,
            data.result
        );

        updateKeyboard(
            guess,
            data.result
        );

        currentRow++;

        currentCol = 0;

        updateAttemptCounter();

        if (data.game_over) {

            gameOver = true;

            setTimeout(() => {

                if (data.won) {

                    showWinScreen(data.answer);

                } else {

                    showLossScreen(data.answer);

                }

            }, 700);

        }

    } catch (error) {

        console.error(error);

        showMessage(
            "Unable to contact the server."
        );
    }
}


/* ================================================================
   APPLY RESULT TO BOARD
   ================================================================ */

function applyResult(row, result) {

    for (let col = 0; col < 5; col++) {

        const tile = getTile(row, col);

        if (!tile) {
            continue;
        }

        tile.classList.remove(
            "correct",
            "present",
            "absent"
        );

        tile.classList.add(result[col]);
    }
}


/* ================================================================
   KEYBOARD
   ================================================================ */

/* ================================================================
   DYNAMIC KEYBOARD LAYOUT

   The puzzle rectangle is NOT changed.

   This reads the actual bottom edge of #game-board and uses the
   remaining visible screen area for the keyboard.
   ================================================================ */

function layoutKeyboard() {

    const app = document.getElementById("wordle-app");
    const gameBoard = document.getElementById("game-board");
    const keyboard = document.getElementById("keyboard");

    if (!app || !gameBoard || !keyboard) {
        return;
    }


    /* ------------------------------------------------------------
       MEASURE THE ACTUAL PUZZLE RECTANGLE
       ------------------------------------------------------------ */

    const appRect =
        app.getBoundingClientRect();

    const boardRect =
        gameBoard.getBoundingClientRect();


    /*
     * Convert the board position from viewport coordinates
     * into #wordle-app coordinates.
     */
    const boardBottom =
        boardRect.bottom - appRect.top;


    /* ------------------------------------------------------------
       DEVICE-SPECIFIC SETTINGS
       ------------------------------------------------------------ */

    const appWidth =
        app.clientWidth;

    let boardKeyboardGap;
    let bottomInset;
    let preferredRowHeight;
    let rowGap;


    if (appWidth === 375) {

        /* iPhone 8 */

        boardKeyboardGap = 12;
        bottomInset = 8;

        preferredRowHeight = 40;
        rowGap = 4;

    } else if (appWidth === 390) {

        /* iPhone 13 */

        boardKeyboardGap = 12;
        bottomInset = 12;

        preferredRowHeight = 47;
        rowGap = 5;

    } else if (appWidth === 768) {

        /* iPad mini 2 */

        boardKeyboardGap = 18;
        bottomInset = 15;

        preferredRowHeight = 64;
        rowGap = 8;

    } else {

        /*
         * Unknown device.
         * Use conservative defaults.
         */

        boardKeyboardGap = 12;
        bottomInset = 8;

        preferredRowHeight = 40;
        rowGap = 4;
    }


    /* ------------------------------------------------------------
       KEYBOARD POSITION
       ------------------------------------------------------------ */

    const keyboardTop =
        Math.ceil(
            boardBottom + boardKeyboardGap
        );


    /* ------------------------------------------------------------
       AVAILABLE SPACE BELOW PUZZLE
       ------------------------------------------------------------ */

    const availableHeight =
        app.clientHeight
        - keyboardTop
        - bottomInset;


    if (availableHeight <= 0) {

        keyboard.style.visibility =
            "hidden";

        console.warn(
            "Wordle keyboard: no space below puzzle.",
            {
                appHeight: app.clientHeight,
                boardBottom,
                keyboardTop,
                availableHeight
            }
        );

        return;
    }


    /* ------------------------------------------------------------
       CALCULATE ROW HEIGHT
       ------------------------------------------------------------ */

    let rowHeight =
        Math.floor(
            (
                availableHeight
                - (rowGap * 2)
            ) / 3
        );


    /*
     * Never make the keyboard keys larger than the
     * device-specific preferred size.
     */
    rowHeight =
        Math.min(
            rowHeight,
            preferredRowHeight
        );


    if (rowHeight < 20) {

        keyboard.style.visibility =
            "hidden";

        console.warn(
            "Wordle keyboard: calculated row height too small.",
            {
                rowHeight,
                availableHeight
            }
        );

        return;
    }


    /* ------------------------------------------------------------
       TOTAL KEYBOARD HEIGHT
       ------------------------------------------------------------ */

    const keyboardHeight =
        (rowHeight * 3)
        + (rowGap * 2);


    /* ------------------------------------------------------------
       APPLY KEYBOARD POSITION
       ------------------------------------------------------------ */

    keyboard.style.position =
        "absolute";

    keyboard.style.left =
        "0";

    keyboard.style.top =
        `${keyboardTop}px`;

    keyboard.style.bottom =
        "auto";

    keyboard.style.width =
        `${app.clientWidth}px`;

    keyboard.style.height =
        `${keyboardHeight}px`;

    keyboard.style.display =
        "flex";

    keyboard.style.flexDirection =
        "column";

    keyboard.style.justifyContent =
        "flex-start";

    keyboard.style.visibility =
        "visible";


    /* ------------------------------------------------------------
       LAYOUT THE THREE KEYBOARD ROWS
       ------------------------------------------------------------ */

    const rows =
        keyboard.querySelectorAll(
            ".keyboard-row"
        );


    rows.forEach((row, index) => {

        row.style.display =
            "flex";

        row.style.flexShrink =
            "0";

        row.style.height =
            `${rowHeight}px`;

        row.style.minHeight =
            `${rowHeight}px`;

        row.style.flex =
            `0 0 ${rowHeight}px`;

        row.style.marginBottom =
            index < rows.length - 1
                ? `${rowGap}px`
                : "0";


        const rowKeys =
            row.querySelectorAll(".key");


        rowKeys.forEach(key => {

            key.style.height =
                `${rowHeight}px`;

            key.style.minHeight =
                `${rowHeight}px`;

            key.style.flexShrink =
                "0";
        });
    });


    /* ------------------------------------------------------------
       DIAGNOSTICS
       ------------------------------------------------------------ */

    console.log(
        "Wordle keyboard layout:",
        {
            appWidth:
                app.clientWidth,

            appHeight:
                app.clientHeight,

            boardTop:
                Math.round(
                    boardRect.top - appRect.top
                ),

            boardBottom:
                Math.round(boardBottom),

            keyboardTop,

            gap:
                keyboardTop - boardBottom,

            availableHeight,

            rowHeight,

            rowGap,

            keyboardHeight,

            keyboardBottom:
                keyboardTop + keyboardHeight,

            remainingBottomSpace:
                app.clientHeight
                - keyboardTop
                - keyboardHeight,

            rows:
                rows.length
        }
    );
}

/* ================================================================
   INITIALISE DYNAMIC KEYBOARD
   ================================================================ */

function initialiseKeyboardLayout() {

    /*
     * First calculation.
     *
     * requestAnimationFrame allows the browser to finish calculating
     * the puzzle's CSS geometry before we measure it.
     */
    requestAnimationFrame(
        () => {
            layoutKeyboard();
        }
    );


    /*
     * Recalculate if the normal viewport changes.
     */
    window.addEventListener(
        "resize",
        layoutKeyboard,
        {
            passive: true
        }
    );


    /*
     * Especially important for iPhone/iPad Safari.
     */
    if (window.visualViewport) {

        window.visualViewport.addEventListener(
            "resize",
            layoutKeyboard,
            {
                passive: true
            }
        );
    }
}

function initialiseKeyboard() {

    keys.forEach(key => {

        key.addEventListener(
            "click",
            () => {

                const value =
                    key.dataset.key;

                handleKey(value);
            }
        );
    });
}


function initialisePhysicalKeyboard() {

    document.addEventListener(
        "keydown",
        event => {

            if (event.key === "Backspace") {

                event.preventDefault();

                handleKey("backspace");

                return;
            }

            if (event.key === "Enter") {

                event.preventDefault();

                handleKey("enter");

                return;
            }

            if (/^[a-zA-Z]$/.test(event.key)) {

                event.preventDefault();

                handleKey(
                    event.key.toLowerCase()
                );
            }
        }
    );
}


function handleKey(key) {

    if (gameOver) {
        return;
    }

    if (key === "backspace") {

        deleteLetter();

        return;
    }

    if (key === "enter") {

        submitGuess();

        return;
    }

    enterLetter(key);
}


/* ================================================================
   KEYBOARD RESULT COLOURS
   ================================================================ */

function updateKeyboard(guess, result) {

    for (let i = 0; i < guess.length; i++) {

        const letter = guess[i];

        const key = document.querySelector(
            `.key[data-key="${letter}"]`
        );

        if (!key) {
            continue;
        }

        const newState = result[i];

        /*
         * Never downgrade:
         *
         * correct > present > absent
         */

        if (
            key.classList.contains("correct")
        ) {
            continue;
        }

        if (
            key.classList.contains("present") &&
            newState === "absent"
        ) {
            continue;
        }

        key.classList.remove(
            "correct",
            "present",
            "absent"
        );

        key.classList.add(newState);
    }
}


function resetKeyboard() {

    keys.forEach(key => {

        key.classList.remove(
            "correct",
            "present",
            "absent"
        );
    });
}


/* ================================================================
   ATTEMPT COUNTER
   ================================================================ */

function updateAttemptCounter() {

    attemptCounter.textContent =
        `${Math.min(currentRow, 6)} / 6`;
}


/* ================================================================
   MESSAGE
   ================================================================ */

let messageTimer = null;


function showMessage(message) {

    messageArea.textContent = message;

    messageArea.classList.add("show");

    clearTimeout(messageTimer);

    messageTimer = setTimeout(() => {

        messageArea.classList.remove("show");

    }, 1600);
}


function clearMessage() {

    messageArea.classList.remove("show");

    clearTimeout(messageTimer);
}


/* ================================================================
   WIN SCREEN
   ================================================================ */

function showWinScreen(answer) {

    resultSymbol.textContent = "🎉";

    resultTitle.textContent =
        "CONGRATULATIONS!";

    resultText.textContent =
        "You found the word.";

    answerDisplay.textContent =
        answer.toUpperCase();

    overlay.classList.remove("hidden");
}


/* ================================================================
   LOSS SCREEN
   ================================================================ */

function showLossScreen(answer) {

    resultSymbol.textContent = "😔";

    resultTitle.textContent =
        "GAME OVER";

    resultText.textContent =
        "The correct word was:";

    answerDisplay.textContent =
        answer.toUpperCase();

    overlay.classList.remove("hidden");
}


/* ================================================================
   OVERLAY
   ================================================================ */

function hideOverlay() {

    overlay.classList.add("hidden");
}
