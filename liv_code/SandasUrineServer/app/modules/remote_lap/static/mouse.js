"use strict";


    const pad =
        document.getElementById(
            "mousePad"
        );



    const backButton =
        document.getElementById(
            "backButton"
        );


    const fullscreenButton =
        document.getElementById(
            "fullscreenButton"
        );


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

    backButton.addEventListener(
        "click",
        (event) => {

            event.stopPropagation();

            window.location.href =
                "/remote_lap/";

        }
    );


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

                }

                else {

                    await document.exitFullscreen();

                }

            }

            catch (error) {

                console.log(
                    "Fullscreen unavailable:",
                    error
                );

            }

        }
    );


/* ========================================================
   TOUCH / GESTURE HANDLING
   ======================================================== */

let fingers = new Map();

let gestureMode = "none";
// "none"
// "move"
// "scroll"

let startTime = 0;
let lastTapTime = 0;

const MOVE_THRESHOLD = 10;
const TAP_TIME = 400;


/* ========================================================
   TOUCH START
   ======================================================== */

pad.addEventListener(
    "touchstart",
    event => {

        event.preventDefault();

        const now = performance.now();

        /*
         * If this is the first finger, start a new gesture.
         */
        if (fingers.size === 0) {

            startTime = now;
            gestureMode = "move";
        }

        /*
         * Add all newly changed fingers.
         */
        for (const touch of event.changedTouches) {

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
         * As soon as two fingers are present,
         * switch permanently to SCROLL mode
         * for this gesture.
         */
        if (fingers.size >= 2) {

            gestureMode = "scroll";
        }
    },
    {
        passive: false
    }
);


/* ========================================================
   TOUCH MOVE
   ======================================================== */

pad.addEventListener(
    "touchmove",
    event => {


        event.preventDefault();


        /*
         * --------------------------------------------------
         * ONE-FINGER MODE
         * --------------------------------------------------
         */

        if (
            gestureMode === "move" &&
            fingers.size === 1
        ) {

            for (const touch of event.changedTouches) {

                const finger =
                    fingers.get(touch.identifier);

                if (!finger) {
                    continue;
                }

                const dx =
                    touch.clientX -
                    finger.lastX;

                const dy =
                    touch.clientY -
                    finger.lastY;


                socket.emit(
                    "mouse_move",
                    {
                        dx: dx,
                        dy: dy
                    }
                );


                finger.x =
                    touch.clientX;

                finger.y =
                    touch.clientY;

                finger.lastX =
                    touch.clientX;

                finger.lastY =
                    touch.clientY;
            }

            return;
        }


        /*
         * --------------------------------------------------
         * TWO-FINGER SCROLL MODE
         * --------------------------------------------------
         */

        if (
            gestureMode === "scroll" &&
            fingers.size === 2
        ) {

            /*
             * Update the positions of the
             * fingers first.
             */
            for (const touch of event.changedTouches) {

                const finger =
                    fingers.get(touch.identifier);

                if (!finger) {
                    continue;
                }

                finger.x =
                    touch.clientX;

                finger.y =
                    touch.clientY;
            }


            const points =
                [...fingers.values()];

            if (points.length !== 2) {
                return;
            }


            /*
             * Average Y position of both fingers.
             */
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
                currentY -
                previousY;


            /*
             * Only generate scroll when
             * movement is significant.
             */
            if (Math.abs(dy) > 1) {

                socket.emit(
                    "mouse_scroll",
                    {
                        amount: -dy
                    }
                );
            }


            /*
             * Save current position for
             * the next scroll event.
             */
            for (const finger of points) {

                finger.lastX =
                    finger.x;

                finger.lastY =
                    finger.y;
            }

            return;
        }
    },
    {
        passive: false
    }
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


        /*
         * Number of fingers involved in
         * this gesture before removing them.
         */
        const fingerCount =
            fingers.size;


        let moved = false;


        /*
         * Check whether any finger moved
         * more than the tap threshold.
         */
        for (const touch of event.changedTouches) {

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


            if (
                Math.abs(dx) > MOVE_THRESHOLD ||
                Math.abs(dy) > MOVE_THRESHOLD
            ) {

                moved = true;
            }
        }


        /*
         * Remove ended fingers.
         */
        for (const touch of event.changedTouches) {

            fingers.delete(
                touch.identifier
            );
        }


        /*
         * --------------------------------------------------
         * ONE-FINGER TAP
         * --------------------------------------------------
         */

        if (
            fingerCount === 1 &&
            gestureMode === "move" &&
            !moved &&
            now - startTime < TAP_TIME
        ) {

            /*
             * Double tap
             */
            if (
                now - lastTapTime < TAP_TIME
            ) {

                socket.emit(
                    "mouse_double_click"
                );

                console.log(
                    "DOUBLE TAP"
                );

                lastTapTime = 0;
            }

            /*
             * Single tap
             */
            else {

                socket.emit(
                    "mouse_click",
                    {
                        button: "left"
                    }
                );

                console.log(
                    "SINGLE TAP"
                );

                lastTapTime = now;
            }
        }


        /*
         * --------------------------------------------------
         * TWO-FINGER TAP
         * --------------------------------------------------
         */

        else if (
            fingerCount === 2 &&
            gestureMode === "scroll" &&
            !moved
        ) {

            socket.emit(
                "mouse_click_right",
                {
                    button: "right"
                }
            );

            console.log(
                "TWO-FINGER TAP"
            );
        }


        /*
         * Reset gesture state after
         * all fingers have left.
         */
        if (fingers.size === 0) {

            gestureMode = "none";
        }
    },
    {
        passive: false
    }
);


/* ========================================================
   PREVENT BROWSER GESTURES
   ======================================================== */

pad.addEventListener(
    "gesturestart",
    event => event.preventDefault(),
    {
        passive: false
    }
);

pad.addEventListener(
    "gesturechange",
    event => event.preventDefault(),
    {
        passive: false
    }
);

pad.addEventListener(
    "gestureend",
    event => event.preventDefault(),
    {
        passive: false
    }
);
