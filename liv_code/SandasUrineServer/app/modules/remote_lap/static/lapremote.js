"use strict";



let touchInputEnabled = true;
let movementTimer = null;

function startTouchInputCycle() {
    setInterval(() => {
        // Disable touch input after 2 seconds
        touchInputEnabled = false;
        console.log("TOUCH INPUT: DISABLED");

        setTimeout(() => {
            // Enable touch input after 1 second
            touchInputEnabled = true;
            console.log("TOUCH INPUT: ENABLED");
        }, 1000);

    }, 3000);
}

//startTouchInputCycle();

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

/*    fullscreenButton.addEventListener(
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

*/


    /* --------------------------------------------------------
       Settings
     --------------------------------------------------------
       Touch state
       -------------------------------------------------------- */

    let fingers = new Map();

    let startTime = 0;

    let lastTapTime = 0;


    /* ========================================================
       TOUCH START
       ======================================================== */


pad.addEventListener(
    "touchstart",
    event => {

        if (!touchInputEnabled) {
            return;
        }
        event.preventDefault();

        const now = performance.now();

        if (fingers.size === 0) {
            startTime = now;
        }

        for (const touch of event.changedTouches) {

            fingers.set(touch.identifier, {
                x: touch.clientX,
                y: touch.clientY,

                lastX: touch.clientX,
                lastY: touch.clientY,

                startX: touch.clientX,
                startY: touch.clientY
            });
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

        if (!touchInputEnabled) {
            return;
        }
        event.preventDefault();

        for (const touch of event.changedTouches) {

            const finger =
                fingers.get(touch.identifier);

            if (!finger) {
                continue;
            }

            const dx =
                touch.clientX - finger.lastX;

            const dy =
                touch.clientY - finger.lastY;
            
            /*if (movementTimer === null){
               movementTimer= startTouchInputCycle();         
            }*/
            /*if (dx !== 0 || dy !== 0) {*/

                socket.emit(
                    "mouse_move",
                    {
                        dx: dx,
                        dy: dy
                    }
                );
            /*}*/


            finger.x = touch.clientX;
            finger.y = touch.clientY;

            finger.lastX = touch.clientX;
            finger.lastY = touch.clientY;
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

        if (!touchInputEnabled) {
            return;
        }
        event.preventDefault();

        const now = performance.now();

        const fingerCount = fingers.size;

        let moved = false;

        /*if (movementTimer !== null) {
            clearInterval(movementTimer);
            movementTimer = null;
        }*/

        /*
         * Determine whether the finger moved significantly.
         */

        for (const touch of event.changedTouches) {

            const finger =
                fingers.get(touch.identifier);

            if (!finger) {
                continue;
            }

            const dx =
                touch.clientX - finger.startX;

            const dy =
                touch.clientY - finger.startY;


            if (
                Math.abs(dx) > 10 ||
                Math.abs(dy) > 10
            ) {
                moved = true;
            }
        }


        /*
         * Remove the fingers.
         */

        for (const touch of event.changedTouches) {
            fingers.delete(touch.identifier);
        }


        /*
         * One-finger tap.
         */

        if (
            fingerCount === 1 &&
            !moved &&
            now - startTime < 400
        ) {

            /*
             * Double click.
             */

            if (
                now - lastTapTime < 400
            ) {
                /*alert("Double Click")*/
                socket.emit(
                    "mouse_double_click"
                );

                console.log("DOUBLE TAP");

                lastTapTime = 0;

            }

            /*
             * Single click.
             */

            else {
                /*alert("Single Click")*/

                socket.emit(
                    "mouse_click",
                    {
                        button: "left"
                    }
                );

                console.log("SINGLE TAP");

                lastTapTime = now;
            }
        }


        /*
         * Two-finger tap = right click.
         */

        else if (
            fingerCount === 2 &&
            !moved
        ) {
            socket.emit(
                "mouse_click_right",
                {
                    button: "right"
                }
            );

            console.log("TWO-FINGER TAP");
        }
    },
    { passive: false }
);

    /* ========================================================
       TOUCH CANCEL
       ======================================================== */



    /* ========================================================
       Context menu
       ======================================================== */

/* ------------------------------------------------------------
   Two-finger scrolling
   ------------------------------------------------------------ */

pad.addEventListener(
    "touchmove",
    event => {

        if (!touchInputEnabled) {
            return;
        }
        if (fingers.size !== 2) {
            return;
        }

        event.preventDefault();

        const points = [...fingers.values()];

        if (points.length !== 2) {
            return;
        }

        const currentY =
            (points[0].y + points[1].y) / 2;

        const previousY =
            (points[0].lastY + points[1].lastY) / 2;

        const dy =
            currentY - previousY;


        if (Math.abs(dy) > 1) {

            socket.emit(
                "mouse_scroll",
                {
                    amount: -dy
                }
            );
        }

    },
    { passive: false }
);


/* ------------------------------------------------------------
   Prevent browser gestures
   ------------------------------------------------------------ */

pad.addEventListener(
    "gesturestart",
    event => event.preventDefault(),
    { passive: false }
);

pad.addEventListener(
    "gesturechange",
    event => event.preventDefault(),
    { passive: false }
);

pad.addEventListener(
    "gestureend",
    event => event.preventDefault(),
    { passive: false }
);

}
