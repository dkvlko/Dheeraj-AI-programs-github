"use strict";


let serverTimeOffset = 0;
let lastHolidayDate = "";


/*
 * ---------------------------------------------------------
 * Socket.IO connection
 * ---------------------------------------------------------
 */

const socket = io();


socket.on("connect", function () {

    console.log("Clock connected to server.");

    socket.emit("clock_time");

});

/* Toggle - Date Details*/
function toggleDateDetails() {

    const overlay =
        document.getElementById(
            "details-overlay"
        );

    const bar =
        document.getElementById(
            "details-bar"
        );

    const frame =
        document.getElementById(
            "details-frame"
        );


    const isOpen =
        overlay.classList.contains(
            "details-open"
        );


    if (!isOpen) {

        /*
         * -------------------------------------------------
         * Refresh the Details page BEFORE displaying it.
         *
         * The timestamp prevents the browser from reusing
         * the previously loaded date_details.html page.
         * -------------------------------------------------
         */

        frame.src =
            "/date-details?refresh=" +
            Date.now();


        /*
         * Open the overlay.
         */

        overlay.classList.add(
            "details-open"
        );


        bar.innerHTML =
            "Hide<br>Details";


    } else {

        /*
         * Close the overlay.
         */

        overlay.classList.remove(
            "details-open"
        );


        bar.innerHTML =
            "See<br>Details";
    }
}

/*Get Is Holiday*/
async function loadHoliday() {

    const holidayElement =
        document.getElementById("holiday");

    try {

        const response =
            await fetch(
                "/holiday-today",
                {
                    method: "GET",
                    cache: "no-store"
                }
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const data =
            await response.json();

        holidayElement.textContent =
            data.answer ||
            "Holiday information unavailable.";

    } catch (error) {

        console.error(
            "Holiday request failed:",
            error
        );

        holidayElement.textContent =
            "Holiday information unavailable.";
    }
}

/*
 * ---------------------------------------------------------
 * Receive server time
 * ---------------------------------------------------------
 */

socket.on("clock_time", function (data) {

    if (
        data &&
        typeof data.timestamp === "number"
    ) {

        serverTimeOffset =
            data.timestamp - Date.now();

    }

    updateClock();

});


/*
 * ---------------------------------------------------------
 * Format date
 * ---------------------------------------------------------
 */

function getDateText() {

    const now =
        new Date(
            Date.now() +
            serverTimeOffset
        );


    return now.toLocaleDateString(
        "en-IN",
        {
            weekday: "long",
            day: "2-digit",
            month: "long",
            year: "numeric"
        }
    ).toUpperCase();

}


/*
 * ---------------------------------------------------------
 * Format time
 * ---------------------------------------------------------
 */

function getTimeText() {

    const now =
        new Date(
            Date.now() +
            serverTimeOffset
        );


    return now.toLocaleTimeString(
        "en-IN",
        {
            hour: "numeric",
            minute: "2-digit",
            second: "2-digit",
            hour12: true
        }
    );

}


/*
 * ---------------------------------------------------------
 * Update display
 * ---------------------------------------------------------
 */

function updateClock() {

    const now =
        new Date(
            Date.now() +
            serverTimeOffset
        );

    const currentDate =
        now.toLocaleDateString(
            "en-CA"
        );


    document.getElementById(
        "date"
    ).textContent =
        getDateText();


    document.getElementById(
        "time"
    ).textContent =
        getTimeText();


    /*
     * -----------------------------------------------------
     * Detect change of calendar date
     * -----------------------------------------------------
     */

    if (
        lastHolidayDate !== "" &&
        lastHolidayDate !== currentDate
    ) {

        console.log(
            "New calendar day detected."
        );

        console.log(
            "Refreshing holiday information..."
        );

        loadHoliday();
    }


    /*
     * Remember today's date
     */

    lastHolidayDate = currentDate;
}

/*
 * ---------------------------------------------------------
 * Update every second
 * ---------------------------------------------------------
 */

setInterval(
    updateClock,
    1000
);


/*
 * Initial display
 */

updateClock();
loadHoliday();
