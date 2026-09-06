const keyElements = document.querySelectorAll("#keyboard .key");

keyElements.forEach((keyElement) => {

    keyElement.addEventListener("click", () => {

        const key = keyElement.dataset.key;

        switch (key) {

            // -------------------------------------------------
            // FUNCTION KEYS
            // -------------------------------------------------

            case "Esc":
                socket.emit("keyboard_key", { key: "Escape" });
                break;

            case "F1":
                socket.emit("keyboard_key", { key: "F1" });
                break;

            case "F2":
                socket.emit("keyboard_key", { key: "F2" });
                break;

            case "F3":
                socket.emit("keyboard_key", { key: "F3" });
                break;

            case "F4":
                socket.emit("keyboard_key", { key: "F4" });
                break;

            case "F5":
                socket.emit("keyboard_key", { key: "F5" });
                break;

            case "F6":
                socket.emit("keyboard_key", { key: "F6" });
                break;

            case "F7":
                socket.emit("keyboard_key", { key: "F7" });
                break;

            case "F8":
                socket.emit("keyboard_zoom");
                break;

            case "F9":
                socket.emit("keyboard_key", { key: "F9" });
                break;

            case "F10":
                socket.emit("keyboard_key", { key: "F10" });
                break;

            case "F11":
                socket.emit("keyboard_key", { key: "F11" });
                break;

            case "F12":
                socket.emit("keyboard_key", { key: "F12" });
                break;


            // -------------------------------------------------
            // SYSTEM KEYS
            // -------------------------------------------------

            case "PrintScreen":
                socket.emit("keyboard_key", { key: "Print" });
                break;

            case "Delete":
                socket.emit("keyboard_key", { key: "Delete" });
                break;

            case "Backspace":
                socket.emit("keyboard_key", { key: "BackSpace" });
                break;

            case "Tab":
                socket.emit("keyboard_key", { key: "Tab" });
                break;

            case "CapsLock":
                socket.emit("keyboard_key", { key: "Caps_Lock" });
                break;

            case "Enter":
                socket.emit("keyboard_key", { key: "Return" });
                break;


            // -------------------------------------------------
            // NUMBER ROW
            // -------------------------------------------------

            case "grave":
                socket.emit("keyboard_key", { key: "grave" });
                break;

            case "1":
                socket.emit("keyboard_key", { key: "1" });
                break;

            case "2":
                socket.emit("keyboard_key", { key: "2" });
                break;

            case "3":
                socket.emit("keyboard_key", { key: "3" });
                break;

            case "4":
                socket.emit("keyboard_key", { key: "4" });
                break;

            case "5":
                socket.emit("keyboard_key", { key: "5" });
                break;

            case "6":
                socket.emit("keyboard_key", { key: "6" });
                break;

            case "7":
                socket.emit("keyboard_key", { key: "7" });
                break;

            case "8":
                socket.emit("keyboard_key", { key: "8" });
                break;

            case "9":
                socket.emit("keyboard_key", { key: "9" });
                break;

            case "0":
                socket.emit("keyboard_key", { key: "0" });
                break;

            case "minus":
                socket.emit("keyboard_key", { key: "minus" });
                break;

            case "equal":
                socket.emit("keyboard_key", { key: "equal" });
                break;


            // -------------------------------------------------
            // QWERTY ROW
            // -------------------------------------------------

            case "q":
                socket.emit("keyboard_key", { key: "q" });
                break;

            case "w":
                socket.emit("keyboard_key", { key: "w" });
                break;

            case "e":
                socket.emit("keyboard_key", { key: "e" });
                break;

            case "r":
                socket.emit("keyboard_key", { key: "r" });
                break;

            case "t":
                socket.emit("keyboard_key", { key: "t" });
                break;

            case "y":
                socket.emit("keyboard_key", { key: "y" });
                break;

            case "u":
                socket.emit("keyboard_key", { key: "u" });
                break;

            case "i":
                socket.emit("keyboard_key", { key: "i" });
                break;

            case "o":
                socket.emit("keyboard_key", { key: "o" });
                break;

            case "p":
                socket.emit("keyboard_key", { key: "p" });
                break;

            case "leftBracket":
                socket.emit("keyboard_key", { key: "bracketleft" });
                break;

            case "rightBracket":
                socket.emit("keyboard_key", { key: "bracketright" });
                break;

            case "backslash":
                socket.emit("keyboard_key", { key: "backslash" });
                break;


            // -------------------------------------------------
            // HOME ROW
            // -------------------------------------------------

            case "a":
                socket.emit("keyboard_key", { key: "a" });
                break;

            case "s":
                socket.emit("keyboard_key", { key: "s" });
                break;

            case "d":
                socket.emit("keyboard_key", { key: "d" });
                break;

            case "f":
                socket.emit("keyboard_key", { key: "f" });
                break;

            case "g":
                socket.emit("keyboard_key", { key: "g" });
                break;

            case "h":
                socket.emit("keyboard_key", { key: "h" });
                break;

            case "j":
                socket.emit("keyboard_key", { key: "j" });
                break;

            case "k":
                socket.emit("keyboard_key", { key: "k" });
                break;

            case "l":
                socket.emit("keyboard_key", { key: "l" });
                break;

            case "semicolon":
                socket.emit("keyboard_key", { key: "semicolon" });
                break;

            case "apostrophe":
                socket.emit("keyboard_key", { key: "apostrophe" });
                break;


            // -------------------------------------------------
            // SHIFT ROW
            // -------------------------------------------------

            case "ShiftLeft":
                socket.emit("keyboard_key", { key: "Shift_L" });
                break;

            case "z":
                socket.emit("keyboard_key", { key: "z" });
                break;

            case "x":
                socket.emit("keyboard_key", { key: "x" });
                break;

            case "c":
                socket.emit("keyboard_key", { key: "c" });
                break;

            case "v":
                socket.emit("keyboard_key", { key: "v" });
                break;

            case "b":
                socket.emit("keyboard_key", { key: "b" });
                break;

            case "n":
                socket.emit("keyboard_key", { key: "n" });
                break;

            case "m":
                socket.emit("keyboard_key", { key: "m" });
                break;

            case "comma":
                socket.emit("keyboard_key", { key: "comma" });
                break;

            case "period":
                socket.emit("keyboard_key", { key: "period" });
                break;

            case "slash":
                socket.emit("keyboard_key", { key: "slash" });
                break;

            case "ShiftRight":
                socket.emit("keyboard_key", { key: "Shift_R" });
                break;


            // -------------------------------------------------
            // CTRL / ALT / SUPER
            // -------------------------------------------------

            case "ControlLeft":
                socket.emit("keyboard_key", { key: "Control_L" });
                break;

            case "ControlRight":
                socket.emit("keyboard_key", { key: "Control_R" });
                break;

            case "AltLeft":
                socket.emit("keyboard_key", { key: "Alt_L" });
                break;

            case "AltRight":
                socket.emit("keyboard_key", { key: "Alt_R" });
                break;

            case "SuperLeft":
                socket.emit("keyboard_key", { key: "Super_L" });
                break;


            // -------------------------------------------------
            // ARROW KEYS
            // -------------------------------------------------

            case "ArrowLeft":
                socket.emit("keyboard_key", { key: "Left" });
                break;

            case "ArrowUp":
                socket.emit("keyboard_key", { key: "Up" });
                break;

            case "ArrowDown":
                socket.emit("keyboard_key", { key: "Down" });
                break;

            case "ArrowRight":
                socket.emit("keyboard_key", { key: "Right" });
                break;


            // -------------------------------------------------
            // SPACE
            // -------------------------------------------------

            case "Space":
                socket.emit("keyboard_key", { key: "space" });
                break;


            // -------------------------------------------------
            // UNKNOWN / NOT IMPLEMENTED
            // -------------------------------------------------

            default:
                console.log("Not implemented:", key);
                break;
        }
    });
});
