"use strict";

const socket = io();


/* =========================================================
   STATUS
   ========================================================= */

const statusDot =
    document.getElementById("statusDot");

const statusText =
    document.getElementById("statusText");

const toast =
    document.getElementById("toast");

let toastTimer = null;


function setStatus(state, message) {

    statusDot.className =
        "statusDot " + state;

    statusText.textContent =
        message;
}


function showToast(message) {

    toast.textContent = message;

    toast.classList.add("show");

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {

        toast.classList.remove("show");

    }, 1800);
}


/* =========================================================
   SOCKET.IO CONNECTION
   ========================================================= */

socket.on("connect", () => {

    console.log(
        "Android TV remote connected:",
        socket.id
    );

    setStatus(
        "busy",
        "Checking TV…"
    );

    sendCommand("status");
});


socket.on("disconnect", () => {

    setStatus(
        "offline",
        "Server offline"
    );

});


socket.on("connect_error", (error) => {

    console.error(
        "TV remote Socket.IO error:",
        error
    );

    setStatus(
        "offline",
        "Server error"
    );

});


socket.on("tv_remote_result", (result) => {

    if (!result) {
        return;
    }

    if (result.ok) {

        if (result.command === "status") {

            setStatus(
                "online",
                "TV connected"
            );

        } else {

            setStatus(
                "online",
                "TV ready"
            );

        }

        return;
    }


    setStatus(
        "offline",
        "TV unavailable"
    );

    showToast(
        result.error ||
        "TV command failed"
    );

    console.error(
        "TV remote error:",
        result
    );
});


/* =========================================================
   COMMAND
   ========================================================= */

function sendCommand(command, extra = {}) {

    if (!socket.connected) {

        showToast(
            "Remote server is not connected"
        );

        return;
    }

    socket.emit(
        "tv_remote_command",
        {
            command: command,
            ...extra
        }
    );
}


/* =========================================================
   NORMAL REMOTE BUTTONS
   ========================================================= */

const commandButtons =
    document.querySelectorAll(
        "[data-command]"
    );


commandButtons.forEach((button) => {

    button.addEventListener(
        "click",
        () => {

            const command =
                button.dataset.command;

            sendCommand(command);

        }
    );

});


/* =========================================================
   APPLICATION BUTTONS
   ========================================================= */

const appButtons =
    document.querySelectorAll(
        "[data-package]"
    );


appButtons.forEach((button) => {

    button.addEventListener(
        "click",
        () => {

            const packageName =
                button.dataset.package;

            sendCommand(
                "launch_app",
                {
                    package: packageName
                }
            );

        }
    );

});


/* =========================================================
   TEXT ENTRY
   ========================================================= */

const textInput =
    document.getElementById(
        "tvTextInput"
    );

const sendTextButton =
    document.getElementById(
        "sendTextButton"
    );


function sendTVText() {

    const value =
        textInput.value;

    if (!value) {
        return;
    }

    sendCommand(
        "type_text",
        {
            text: value
        }
    );

    textInput.value = "";
}


sendTextButton.addEventListener(
    "click",
    sendTVText
);


textInput.addEventListener(
    "keydown",
    (event) => {

        if (event.key === "Enter") {

            event.preventDefault();

            sendTVText();

        }

    }
);


/* =========================================================
   FULLSCREEN
   ========================================================= */

document
    .getElementById("fullscreenButton")
    .addEventListener(
        "click",
        async () => {

            try {

                if (
                    document.documentElement
                        .requestFullscreen
                ) {

                    await document.documentElement
                        .requestFullscreen();

                }

                else if (
                    document.documentElement
                        .webkitRequestFullscreen
                ) {

                    document.documentElement
                        .webkitRequestFullscreen();

                }

            } catch (error) {

                console.log(
                    "Fullscreen unavailable:",
                    error
                );

            }

        }
    );


/* =========================================================
   BACK TO LAPTOP REMOTE
   ========================================================= */

document
    .getElementById("tvBackButton")
    .addEventListener(
        "click",
        () => {

            window.location.href =
                "/remote_lap/";

        }
    );


/* =========================================================
   PREVENT LONG-PRESS CONTEXT MENU
   ========================================================= */

document
    .getElementById("tvRemoteScreen")
    .addEventListener(
        "contextmenu",
        (event) => {

            if (
                event.target.tagName !== "INPUT" &&
                event.target.tagName !== "TEXTAREA"
            ) {

                event.preventDefault();

            }

        }
    );


/* =========================================================
   OPTIONAL PHYSICAL KEYBOARD SUPPORT
   Useful when the same page is opened on a laptop.
   ========================================================= */

document.addEventListener(
    "keydown",
    (event) => {

        if (
            event.target &&
            event.target.tagName === "INPUT" ||
            event.target.tagName === "TEXTAREA"
        ) {
            return;
        }

        const keyMap = {

            ArrowUp: "up",
            ArrowDown: "down",
            ArrowLeft: "left",
            ArrowRight: "right",

            Enter: "select",
            Escape: "back",

            Home: "home",

            AudioVolumeUp: "vol_up",
            AudioVolumeDown: "vol_down",
            AudioVolumeMute: "mute"

        };

        const command =
            keyMap[event.key];

        if (command) {

            event.preventDefault();

            sendCommand(command);

        }

    }
);
