#!/usr/bin/env python3

import sqlite3
from datetime import datetime, timedelta


# ============================================================
# Configuration
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"

START_YEAR = 1926
END_YEAR = 2126


# ============================================================
# Helper functions
# ============================================================

def parse_local_datetime(value):
    """
    Parse a local datetime stored in either of these forms:

        2004-03-29 18:23:16
        2004-03-21T04:11:20.983311+05:30

    Returns a naive datetime representing local clock time.

    For Madhyahna calculations we only need consistent local
    clock times, so timezone offset is deliberately ignored.
    """
    return datetime.fromisoformat(value).replace(tzinfo=None)


def parse_local_time(date_string, time_string):
    """
    Combine a YYYY-MM-DD date with an HH:MM:SS sunrise/sunset time.
    """
    return datetime.strptime(
        f"{date_string} {time_string}",
        "%Y-%m-%d %H:%M:%S"
    )


def calculate_madhyahna(date_string, sunrise_time, sunset_time):
    """
    Your convention:

        Daylight = Sunset - Sunrise

        Madhyahna_Start = Sunrise + 2/5 Daylight
        Madhyahna_End   = Sunrise + 3/5 Daylight
    """

    sunrise = parse_local_time(date_string, sunrise_time)
    sunset = parse_local_time(date_string, sunset_time)

    daylight = sunset - sunrise

    madhyahna_start = sunrise + daylight * 2 / 5
    madhyahna_end = sunrise + daylight * 3 / 5

    return madhyahna_start, madhyahna_end


def intervals_overlap(start1, end1, start2, end2):
    """
    Half-open interval overlap:

        [start1, end1) overlaps [start2, end2)

    """
    return start1 < end2 and end1 > start2


# ============================================================
# Main
# ============================================================

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

try:

    # --------------------------------------------------------
    # Find every Normal Chaitra Shukla Navami
    # --------------------------------------------------------

    navami_query = """
        SELECT
            t.Start_Date_Time_Local AS Navami_Start,
            t.End_Date_Time_Local AS Navami_End,

            m.Start_Date_Time_Local AS Chaitra_Start,
            m.End_Date_Time_Local AS Chaitra_End,

            m.Masa_Number,
            m.Masa_English,
            m.Masa_Hindi,
            m.Masa_Type

        FROM Tithi_Transition t

        JOIN Masa_Transition m
          ON t.Start_Date_Time_UTC < m.End_Date_Time_UTC
         AND t.End_Date_Time_UTC > m.Start_Date_Time_UTC

        WHERE t.Tithi = '09'
          AND t.Paksha = 'Shukla'

          AND m.Masa_English = 'Chaitra'
          AND m.Masa_Type = 'Normal'

          AND t.Start_Date_Time_Local >= ?
          AND t.Start_Date_Time_Local < ?

        ORDER BY t.Start_Date_Time_Local
    """

    start_date = f"{START_YEAR:04d}-01-01"
    end_date = f"{END_YEAR + 1:04d}-01-01"

    navami_rows = conn.execute(
        navami_query,
        (start_date, end_date)
    ).fetchall()

    print(f"Found {len(navami_rows)} Chaitra Shukla Navami intervals.")
    print()

    # --------------------------------------------------------
    # Process each Navami
    # --------------------------------------------------------

    inserted = 0

    for navami in navami_rows:

        navami_start = parse_local_datetime(navami["Navami_Start"])
        navami_end = parse_local_datetime(navami["Navami_End"])

        print("=" * 72)
        print(
            f"Navami: {navami_start} -> {navami_end}"
        )

        # Navami can span two civil dates.
        #
        # Test the date on which Navami starts and the date on
        # which Navami ends.
        #
        # Usually these are consecutive dates.
        candidate_dates = sorted({
            navami_start.date(),
            navami_end.date()
        })

        qualifying_dates = []

        for candidate_date in candidate_dates:

            date_string = candidate_date.isoformat()

            # ------------------------------------------------
            # Get sunrise and sunset for this civil date
            # ------------------------------------------------

            sun = conn.execute(
                """
                SELECT
                    Sunrise_Time,
                    Sunset_Time
                FROM Sun_Position
                WHERE Date = ?
                  AND Location = ?
                """,
                (date_string, LOCATION)
            ).fetchone()

            if sun is None:
                print(
                    f"  WARNING: No Sun_Position for {date_string}"
                )
                continue

            # ------------------------------------------------
            # Calculate Madhyahna
            # ------------------------------------------------

            madhyahna_start, madhyahna_end = calculate_madhyahna(
                date_string,
                sun["Sunrise_Time"],
                sun["Sunset_Time"]
            )

            # ------------------------------------------------
            # Does Navami prevail during Madhyahna?
            # ------------------------------------------------

            overlap = intervals_overlap(
                navami_start,
                navami_end,
                madhyahna_start,
                madhyahna_end
            )

            print(
                f"  {date_string}: "
                f"Sunrise={sun['Sunrise_Time']} "
                f"Sunset={sun['Sunset_Time']} "
                f"Madhyahna={madhyahna_start.time()} "
                f"-> {madhyahna_end.time()} "
                f"Navami_Vyapini={overlap}"
            )

            if overlap:
                qualifying_dates.append(
                    (
                        candidate_date,
                        madhyahna_start,
                        madhyahna_end
                    )
                )

        # ----------------------------------------------------
        # Rama Navami selection
        #
        # If Navami prevails during Madhyahna on both dates,
        # select the earlier date.
        # ----------------------------------------------------

        if not qualifying_dates:
            print("  RESULT: No Madhyahna-vyapini date found.")
            continue

        qualifying_dates.sort(key=lambda x: x[0])

        festival_date, madhyahna_start, madhyahna_end = (
            qualifying_dates[0]
        )

        date_string = festival_date.isoformat()

        print(
            f"  RESULT: Rama Navami = {date_string}"
        )

        # ----------------------------------------------------
        # Store the selected Rama Navami
        # ----------------------------------------------------

        conn.execute(
            """
            INSERT OR REPLACE INTO Rama_Navami (
                Date,
                Location,
                Navami_Start_Local,
                Navami_End_Local,
                Madhyahna_Start,
                Madhyahna_End
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                date_string,
                LOCATION,
                navami["Navami_Start"],
                navami["Navami_End"],
                madhyahna_start.isoformat(
                    timespec="seconds"
                ),
                madhyahna_end.isoformat(
                    timespec="seconds"
                )
            )
        )

        inserted += 1

    conn.commit()

    print()
    print("=" * 72)
    print(f"Inserted/updated {inserted} Rama Navami records.")

finally:
    conn.close()
