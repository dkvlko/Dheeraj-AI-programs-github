"use strict";


/* ============================================================
   LANDING PAGE
   ============================================================ */

if (window.REMOTE_PAGE === "remote") {

    const mouseButton =
        document.getElementById("mouseButton");

    const keyboardButton =
        document.getElementById("keyboardButton");


    mouseButton.addEventListener("click", () => {

        window.location.href =
            "/remote_lap/lapmouse";
    });


    keyboardButton.addEventListener("click", () => {

        alert("Keyboard remote is not implemented yet.");
    });
}


/* ============================================================
   MOUSEPAD
   ============================================================ */

if (window.REMOTE_PAGE === "mouse") {

    const pad =
        document.getElementById("mousePad");

    const backButton =
        document.getElementById("backButton");

    const fullscreenButton =
        document.getElementById("fullscreenButton");


    /* --------------------------------------------------------
       Socket.IO
       -------------------------------------------------------- */

    const socket = io();


    socket.on("connect", () => {

        console.log(
            "Mouse remote connected:",
            socket.id
        );

    });


    socket.on("disconnect", () => {

        console.log(
            "Mouse remote disconnected"
        );

    });


    /* --------------------------------------------------------
       Navigation
       -------------------------------------------------------- */

    backButton.addEventListener("click", (event) => {

        event.stopPropagation();

        window.location.href =
            "/remote_lap/";
    });


    /* --------------------------------------------------------
       Fullscreen
       -------------------------------------------------------- */

    fullscreenButton.addEventListener(
        "click",
        async (event) => {

            event.stopPropagation();

            try {

                if (!document.fullscreenElement) {

                    await document.documentElement
                        .requestFullscreen();

                } else {

                    await document.exitFullscreen();
                }

            } catch (error) {

                console.log(
                    "Fullscreen unavailable:",
                    error
                );
            }

        }
    );


    /* --------------------------------------------------------
       Prevent browser gestures
       -------------------------------------------------------- */

    document.addEventListener(
        "touchmove",
        event => event.preventDefault(),
        { passive: false }
    );


    document.addEventListener(
        "gesturestart",
        event => event.preventDefault(),
        { passive: false }
    );


    document.addEventListener(
        "gesturechange",
        event => event.preventDefault(),
        { passive: false }
    );


    document.addEventListener(
        "gestureend",
        event => event.preventDefault(),
        { passive: false }
    );


    /* --------------------------------------------------------
       Settings
       -------------------------------------------------------- */
    const SCREEN_WIDTH = 1366;
    const SCREEN_HEIGHT = 768;


    let remoteCursorX = 683;
    let remoteCursorY = 384;
    const MOUSE_SENSITIVITY = 1.5;


    const SCROLL_SENSITIVITY = 1;


    /* --------------------------------------------------------
       Touch state
       -------------------------------------------------------- */

    let fingers = new Map();

    let startTime = 0;

    let lastTapTime = 0;

    let gestureStarted = false;


    /* ========================================================
       TOUCH START
       ======================================================== */

    pad.addEventListener(
        "touchstart",
        event => {

            event.preventDefault();

            const now =
                performance.now();


            if (fingers.size === 0) {

                startTime = now;

                gestureStarted = false;
            }


            for (
                const touch of event.changedTouches
            ) {

                fingers.set(
                    touch.identifier,
                    {

                        x: touch.clientX,
                        y: touch.clientY,

                        lastX: touch.clientX,
                        lastY: touch.clientY,

                        startX: touch.clientX,
                        startY: touch.clientY
                    }
                );
            }


            /*
             * Two fingers means scrolling.
             */

            if (fingers.size >= 2) {

                gestureStarted = true;

                for (
                    const finger of fingers.values()
                ) {

                    finger.lastX = finger.x;
                    finger.lastY = finger.y;
                }
            }

        },
        { passive: false }
    );


    /* ========================================================
       TOUCH MOVE
       ======================================================== */

    pad.addEventListener(
        "touchmove",
        event => {

            event.preventDefault();


            /*
             * Update finger positions.
             */

            for (
                const touch of event.changedTouches
            ) {

                const finger =
                    fingers.get(touch.identifier);

                if (!finger) {
                    continue;
                }

                finger.x = touch.clientX;
                finger.y = touch.clientY;
            }


            /* ------------------------------------------------
               ONE FINGER = CURSOR
               ------------------------------------------------ */

            if (fingers.size === 1) {

                const finger =
                    fingers.values()
                        .next()
                        .value;


                const totalDx =
                    finger.x - finger.startX;

                const totalDy =
                    finger.y - finger.startY;


                /*
                 * Ignore tiny involuntary movements.
                 */



                const dx =
                    (finger.x - finger.lastX)
                    * MOUSE_SENSITIVITY;

                const dy =
                    (finger.y - finger.lastY)
                    * MOUSE_SENSITIVITY;
                

                const newX = Math.max(
                    0,
                    Math.min(SCREEN_WIDTH - 1, remoteCursorX + dx)
                );

                const newY = Math.max(
                    0,
                    Math.min(SCREEN_HEIGHT - 1, remoteCursorY + dy)
                );

                const actualDx = newX - remoteCursorX;
                const actualDy = newY - remoteCursorY;

                if (actualDx !== 0 || actualDy !== 0) {
                    socket.emit("mouse_move", {
                        dx: actualDx,
                        dy: actualDy
                    });
                    remoteCursorX = newX;
                    remoteCursorY = newY;

                    gestureStarted = true;
                }



                finger.lastX = finger.x;
                finger.lastY = finger.y;
            }


            /* ------------------------------------------------
               TWO FINGERS = SCROLL
               ------------------------------------------------ */

            else if (fingers.size === 2) {

                const points =
                    [...fingers.values()];


                const currentY =
                    (
                        points[0].y +
                        points[1].y
                    ) / 2;


                const previousY =
                    (
                        points[0].lastY +
                        points[1].lastY
                    ) / 2;


                const dy =
                    currentY - previousY;


                if (Math.abs(dy) > 0.5) {

                    socket.emit(
                        "scroll",
                        {
                            amount:
                                -dy *
                                SCROLL_SENSITIVITY
                        }
                    );
                }


                for (
                    const finger of points
                ) {

                    finger.lastX = finger.x;
                    finger.lastY = finger.y;
                }


                gestureStarted = true;
            }

        },
        { passive: false }
    );


    /* ========================================================
       TOUCH END
       ======================================================== */

    pad.addEventListener(
        "touchend",
        event => {

            event.preventDefault();


            const now =
                performance.now();


            const fingerCount =
                fingers.size;


            /*
             * Determine whether finger moved.
             */

            let moved = false;


            for (
                const touch of event.changedTouches
            ) {

                const finger =
                    fingers.get(touch.identifier);


                if (!finger) {
                    continue;
                }


                const dx =
                    touch.clientX -
                    finger.startX;


                const dy =
                    touch.clientY -
                    finger.startY;


            }


            /*
             * Remove fingers.
             */

            for (
                const touch of event.changedTouches
            ) {

                fingers.delete(
                    touch.identifier
                );
            }


            /* ------------------------------------------------
               ONE FINGER = CLICK / DOUBLE CLICK
               ------------------------------------------------ */

            if (
                fingerCount === 1 &&
                !moved &&
                !gestureStarted
            ) {

                const elapsed =
                    now - startTime;


                if (elapsed < 350) {

                    /*
                     * Double click.
                     */

                    if (
                        now - lastTapTime < 350
                    ) {

                        socket.emit(
                            "mouse_double_click"
                        );

                        lastTapTime = 0;

                    } else {

                        socket.emit(
                            "mouse_click",
                            {
                                button: "left"
                            }
                        );

                        lastTapTime = now;
                    }
                }
            }


            /* ------------------------------------------------
               TWO FINGER TAP = RIGHT CLICK
               ------------------------------------------------ */

            else if (
                fingerCount === 2 &&
                !moved &&
                !gestureStarted
            ) {

                socket.emit(
                    "mouse_click",
                    {
                        button: "right"
                    }
                );
            }


            /* ------------------------------------------------
               THREE FINGER TAP = MIDDLE CLICK
               ------------------------------------------------ */

            else if (
                fingerCount === 3 &&
                !moved &&
                !gestureStarted
            ) {

                socket.emit(
                    "mouse_click",
                    {
                        button: "middle"
                    }
                );
            }


            /*
             * Reset when all fingers are gone.
             */

            if (fingers.size === 0) {

                gestureStarted = false;
            }

        },
        { passive: false }
    );


    /* ========================================================
       TOUCH CANCEL
       ======================================================== */

    pad.addEventListener(
        "touchcancel",
        event => {

            event.preventDefault();

            fingers.clear();

            gestureStarted = false;
        },
        { passive: false }
    );


    /* ========================================================
       Context menu
       ======================================================== */

    pad.addEventListener(
        "contextmenu",
        event => {
            event.preventDefault();
        }
    );

}
