from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"
LATITUDE = 26.8467
LONGITUDE = 80.9462

TIMEZONE = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

# Hindu midnight is NOT ordinary 00:00.
#
# We calculate it as:
#
#       Sunset + (next sunrise - sunset) / 2
#
# i.e. the middle of the local night.
#
# This is the convention used by Panchang calculations.
# ============================================================


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection():
    return sqlite3.connect(DB_PATH)


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def format_dt(value: datetime) -> str:
    return value.isoformat(timespec="microseconds")


# ============================================================
# SUNRISE / SUNSET
# ============================================================

def get_sun_times(conn, date_string: str):
    """
    Get sunrise and sunset from the existing Sun_Position table.

    Sun_Position stores:
        Date         = YYYY-MM-DD
        Sunrise_Time = HH:MM:SS
        Sunset_Time  = HH:MM:SS

    Return timezone-aware datetime objects.
    """

    row = conn.execute(
        """
        SELECT
            Sunrise_Time,
            Sunset_Time
        FROM Sun_Position
        WHERE Date = ?
          AND Location = ?
        """,
        (
            date_string,
            LOCATION,
        ),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            f"No Sun_Position row for {date_string}"
        )

    sunrise_string, sunset_string = row

    sunrise = datetime.fromisoformat(
        f"{date_string}T{sunrise_string}+05:30"
    )

    sunset = datetime.fromisoformat(
        f"{date_string}T{sunset_string}+05:30"
    )

    return sunrise, sunset


def get_hindu_midnight(conn, date_string: str):
    """
    Hindu midnight is the midpoint between:

        sunset on the current date

    and

        sunrise on the following date.
    """

    _, sunset_today = get_sun_times(
        conn,
        date_string,
    )

    current_date = datetime.fromisoformat(
        f"{date_string}T00:00:00+05:30"
    )

    next_date = (
        current_date + timedelta(days=1)
    ).date().isoformat()

    sunrise_next, _ = get_sun_times(
        conn,
        next_date,
    )

    return sunset_today + (
        sunrise_next - sunset_today
    ) / 2

# ============================================================
# PRADOSH
# ============================================================

def get_pradosh(conn, date_string: str):
    """
    Return Pradosh start/end from Daily_Time_Periods.
    """

    row = conn.execute(
        """
        SELECT
            Pradosh_Start,
            Pradosh_End
        FROM Daily_Time_Periods
        WHERE Date = ?
          AND Location = ?
        """,
        (
            date_string,
            LOCATION,
        ),
    ).fetchone()

    if row is None:
        raise RuntimeError(
            f"No Daily_Time_Periods row for {date_string}"
        )

    return parse_dt(row[0]), parse_dt(row[1])


# ============================================================
# PURNIMA
# ============================================================

def get_purnima_intervals(
    conn,
    start_date: str,
    end_date: str,
):
    """
    Find all astronomical Purnima intervals.

    Purnima Tithi is:

        168° <= Sun-Moon separation < 180°

    Therefore in Karana_Transition the Purnima interval
    begins with:

        168 -> 174

    and ends with:

        174 -> 180

    We obtain the complete interval by finding these two
    consecutive Karana rows.
    """

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Angular_Separation_Start,
            Angular_Separation_End,
            Karana_Number,
            Karana,
            Is_Bhadra
        FROM Karana_Transition
        WHERE Location = ?
          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local < ?
          AND (
                Angular_Separation_Start = 168.0
                OR Angular_Separation_End = 180.0
              )
        ORDER BY Start_Date_Time_UTC
        """,
        (
            LOCATION,
            start_date,
            end_date,
        ),
    ).fetchall()

    purnimas = []

    for row in rows:

        (
            start_local,
            end_local,
            angle_start,
            angle_end,
            karana_number,
            karana,
            is_bhadra,
        ) = row

        # 168 -> 174 is Purnima beginning.
        if angle_start == 168.0:

            purnima_start = parse_dt(start_local)

            # Find the 174 -> 180 row beginning exactly
            # where this row ends.
            end_row = conn.execute(
                """
                SELECT
                    End_Date_Time_Local
                FROM Karana_Transition
                WHERE Location = ?
                  AND Start_Date_Time_Local = ?
                  AND Angular_Separation_Start = 174.0
                  AND Angular_Separation_End = 180.0
                """,
                (
                    LOCATION,
                    end_local,
                ),
            ).fetchone()

            if end_row is None:
                raise RuntimeError(
                    "Could not find 174° -> 180° "
                    f"transition after {start_local}"
                )

            purnima_end = parse_dt(end_row[0])

            purnimas.append(
                (
                    purnima_start,
                    purnima_end,
                )
            )

    return purnimas


# ============================================================
# BHADRA
# ============================================================

def get_bhadra_intervals(
    conn,
    start_date: str,
    end_date: str,
):
    """
    Get complete Vishti/Bhadra intervals from
    Karana_Transition.

    Is_Bhadra = 1 is authoritative.
    """

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local
        FROM Karana_Transition
        WHERE Location = ?
          AND Is_Bhadra = 1
          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local < ?
        ORDER BY Start_Date_Time_UTC
        """,
        (
            LOCATION,
            start_date,
            end_date,
        ),
    ).fetchall()

    return [
        (
            parse_dt(row[0]),
            parse_dt(row[1]),
        )
        for row in rows
    ]


# ============================================================
# BHADRA SUB-PERIODS
# ============================================================

def get_bhadra_segments(
    conn,
    start_date: str,
    end_date: str,
):
    """
    Return Bhadra Puccha and Bhadra Mukha intervals from
    Bhadra_Transition.
    """

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Bhadra_Type
        FROM Bhadra_Transition
        WHERE Location = ?
          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local < ?
          AND Bhadra_Type IN (
                'Bhadra_Puccha',
                'Bhadra_Mukha'
              )
        ORDER BY Start_Date_Time_UTC
        """,
        (
            LOCATION,
            start_date,
            end_date,
        ),
    ).fetchall()

    result = []

    for row in rows:
        result.append(
            (
                parse_dt(row[0]),
                parse_dt(row[1]),
                row[2],
            )
        )

    return result


# ============================================================
# INTERVAL OPERATIONS
# ============================================================

def overlaps(
    start1: datetime,
    end1: datetime,
    start2: datetime,
    end2: datetime,
) -> bool:

    return (
        start1 < end2
        and end1 > start2
    )


def intersection(
    start1: datetime,
    end1: datetime,
    start2: datetime,
    end2: datetime,
):
    """
    Return intersection of two intervals.

    Returns None if there is no intersection.
    """

    start = max(start1, start2)
    end = min(end1, end2)

    if start >= end:
        return None

    return start, end


# ============================================================
# PURNIMA CANDIDATE
# ============================================================


def find_holika_candidates(
    conn,
    year: int,
):
    """
    Find the Phalguna Purnima which overlaps Pradosh.

    IMPORTANT:

    We identify the lunar month from the Hindu_Calendar row
    corresponding to the CIVIL DATE on which astronomical
    Purnima begins (168 degrees).

    We do NOT require Tithi = 15 on that date because Purnima
    can begin after sunrise. For example, in 2026 Purnima
    begins on March 2 at about 17:56, while the Tithi at
    sunrise on March 2 is still 14.

    Therefore:

        Purnima start date
              +
        Masa = 12
              +
        Purnima/Pradosh overlap

    determines the Holika candidate.
    """

    search_start = f"{year}-01-01T00:00:00+05:30"
    search_end = f"{year + 1}-01-01T00:00:00+05:30"

    # --------------------------------------------------------
    # Get all astronomical Purnima intervals for this year.
    #
    # Purnima:
    #
    #     168° -> 180°
    #
    # get_purnima_intervals() returns:
    #
    #     (Purnima_Start, Purnima_End)
    # --------------------------------------------------------

    purnimas = get_purnima_intervals(
        conn,
        search_start,
        search_end,
    )

    candidates = []

    for purnima_start, purnima_end in purnimas:

        # ----------------------------------------------------
        # Civil date on which Purnima begins.
        # ----------------------------------------------------

        purnima_date = purnima_start.date().isoformat()

        year_string = purnima_date[0:4]
        month_string = purnima_date[5:7]
        day_string = purnima_date[8:10]

        # ----------------------------------------------------
        # Find the Hindu_Calendar row for EXACTLY the date
        # on which this Purnima begins.
        # ----------------------------------------------------

        calendar_row = conn.execute(
            """
            SELECT
                Tithi,
                Paksha,
                Masa,
                Adhika_Masa
            FROM Hindu_Calendar
            WHERE Year = ?
              AND Month = ?
              AND Date = ?
            """,
            (
                year_string,
                month_string,
                day_string,
            ),
        ).fetchone()

        if calendar_row is None:
            continue

        (
            tithi,
            paksha,
            masa,
            adhika_masa,
        ) = calendar_row

        # ----------------------------------------------------
        # Holika is specifically Phalguna Purnima.
        #
        # In your Amanta system:
        #
        #     Masa 12 = Phalguna
        #
        # We deliberately DO NOT require Tithi = 15 here.
        #
        # Purnima can begin after sunrise, in which case the
        # sunrise Tithi can still be 14.
        # ----------------------------------------------------

        if masa != "12":
            continue

        # ----------------------------------------------------
        # Get Pradosh for the SAME CIVIL DATE on which
        # Purnima begins.
        # ----------------------------------------------------

        try:
            pradosh_start, pradosh_end = get_pradosh(
                conn,
                purnima_date,
            )
        except RuntimeError:
            continue

        # ----------------------------------------------------
        # Purnima must overlap Pradosh.
        #
        # This is the fundamental Holika candidate condition.
        # ----------------------------------------------------

        overlap = intersection(
            purnima_start,
            purnima_end,
            pradosh_start,
            pradosh_end,
        )

        if overlap is None:
            continue

        # ----------------------------------------------------
        # Candidate found.
        # ----------------------------------------------------

        candidates.append(
            {
                "date": purnima_date,

                "purnima_start":
                    purnima_start,

                "purnima_end":
                    purnima_end,

                "pradosh_start":
                    pradosh_start,

                "pradosh_end":
                    pradosh_end,

                "tithi":
                    tithi,

                "paksha":
                    paksha,

                "masa":
                    masa,

                "adhika_masa":
                    adhika_masa,
            }
        )

    # --------------------------------------------------------
    # There should normally be exactly one Phalguna Purnima
    # candidate per Gregorian year.
    # --------------------------------------------------------

    unique = {}

    for candidate in candidates:

        key = (
            candidate["date"],
            candidate["purnima_start"],
        )

        unique[key] = candidate

    return list(unique.values())

# ============================================================
# HOLIKA DAHAN RULE
# ============================================================

def determine_holika_dahan(
    conn,
    candidate: dict,
):
    """
    Determine the Holika Dahan window.

    Rules:

    1. Prefer Pradosh with Purnima and no Bhadra.

    2. If Bhadra overlaps Pradosh but ends before Hindu
       midnight, perform after Bhadra ends.

    3. If Bhadra extends beyond Hindu midnight:
       use Bhadra Puccha if it occurs between Pradosh and
       Hindu midnight.

    4. For the North-Indian/Banaras alternate rule, if
       Bhadra continues beyond midnight, wait until Bhadra
       ends and perform afterward.

    5. Never select Bhadra Mukha.
    """

    date_string = candidate["date"]

    purnima_start = candidate["purnima_start"]
    purnima_end = candidate["purnima_end"]

    pradosh_start = candidate["pradosh_start"]
    pradosh_end = candidate["pradosh_end"]

    # --------------------------------------------------------
    # Sunset / Hindu midnight
    # --------------------------------------------------------

    _, sunset = get_sun_times(
        conn,
        date_string,
    )

    hindu_midnight = get_hindu_midnight(
        conn,
        date_string,
    )

    # --------------------------------------------------------
    # Bhadra intervals around this date.
    #
    # Search from one day before through one day after because
    # Bhadra can cross midnight.
    # --------------------------------------------------------

    day = datetime.fromisoformat(
        date_string + "T00:00:00+05:30"
    )

    search_start = (
        day - timedelta(days=1)
    ).isoformat()

    search_end = (
        day + timedelta(days=2)
    ).isoformat()

    bhadra_intervals = get_bhadra_intervals(
        conn,
        search_start,
        search_end,
    )

    # --------------------------------------------------------
    # Find Bhadra overlapping Pradosh.
    # --------------------------------------------------------

    bhadra = None

    for bhadra_start, bhadra_end in bhadra_intervals:

        if overlaps(
            bhadra_start,
            bhadra_end,
            pradosh_start,
            pradosh_end,
        ):
            bhadra = (
                bhadra_start,
                bhadra_end,
            )
            break

    # ========================================================
    # CASE 1
    #
    # No Bhadra during Pradosh.
    # ========================================================

    if bhadra is None:

        return {
            **candidate,
            "holika_rule":
                "Pradosh_without_Bhadra",
            "holika_start":
                pradosh_start,
            "holika_end":
                pradosh_end,
            "bhadra_start":
                None,
            "bhadra_end":
                None,
            "hindu_midnight":
                hindu_midnight,
        }

    bhadra_start, bhadra_end = bhadra

    # ========================================================
    # CASE 2
    #
    # Bhadra ends before Pradosh ends.
    #
    # Wait until Bhadra is over.
    # ========================================================

    if bhadra_end <= pradosh_end:

        holika_start = max(
            pradosh_start,
            bhadra_end,
        )

        return {
            **candidate,
            "holika_rule":
                "After_Bhadra_During_Pradosh",
            "holika_start":
                holika_start,
            "holika_end":
                pradosh_end,
            "bhadra_start":
                bhadra_start,
            "bhadra_end":
                bhadra_end,
            "hindu_midnight":
                hindu_midnight,
        }

    # ========================================================
    # CASE 3
    #
    # Bhadra continues beyond Pradosh.
    # ========================================================

    if bhadra_end <= hindu_midnight:

        # There is no Bhadra-free part of Pradosh.
        #
        # Wait until Bhadra ends.
        #
        # This is after Pradosh but before Hindu midnight.

        return {
            **candidate,
            "holika_rule":
                "After_Bhadra_Before_Hindu_Midnight",
            "holika_start":
                bhadra_end,
            "holika_end":
                hindu_midnight,
            "bhadra_start":
                bhadra_start,
            "bhadra_end":
                bhadra_end,
            "hindu_midnight":
                hindu_midnight,
        }

    # ========================================================
    # CASE 4
    #
    # Bhadra continues beyond Hindu midnight.
    #
    # First check Bhadra Puccha.
    # ========================================================

    bhadra_segments = get_bhadra_segments(
        conn,
        search_start,
        search_end,
    )

    puccha = None
    mukha = None

    for (
        segment_start,
        segment_end,
        segment_type,
    ) in bhadra_segments:

        if segment_type == "Bhadra_Puccha":

            if overlaps(
                segment_start,
                segment_end,
                pradosh_start,
                hindu_midnight,
            ):
                puccha = (
                    segment_start,
                    segment_end,
                )

        elif segment_type == "Bhadra_Mukha":

            if overlaps(
                segment_start,
                segment_end,
                pradosh_start,
                hindu_midnight,
            ):
                mukha = (
                    segment_start,
                    segment_end,
                )

    # --------------------------------------------------------
    # If Puccha exists between Pradosh and Hindu midnight,
    # this is the preferred conventional fallback.
    # --------------------------------------------------------

    if puccha is not None:

        puccha_start, puccha_end = puccha

        return {
            **candidate,
            "holika_rule":
                "Bhadra_Puccha_During_Pradosh",
            "holika_start":
                puccha_start,
            "holika_end":
                puccha_end,
            "bhadra_start":
                bhadra_start,
            "bhadra_end":
                bhadra_end,
            "bhadra_puccha_start":
                puccha_start,
            "bhadra_puccha_end":
                puccha_end,
            "bhadra_mukha_start":
                mukha[0] if mukha else None,
            "bhadra_mukha_end":
                mukha[1] if mukha else None,
            "hindu_midnight":
                hindu_midnight,
        }

    # ========================================================
    # CASE 5
    #
    # No usable Puccha before Hindu midnight.
    #
    # North-Indian/Banaras alternate rule:
    #
    # wait until Bhadra ends.
    # ========================================================

    return {
        **candidate,
        "holika_rule":
            "After_Bhadra_After_Hindu_Midnight",
        "holika_start":
            bhadra_end,
        "holika_end":
            None,
        "bhadra_start":
            bhadra_start,
        "bhadra_end":
            bhadra_end,
        "bhadra_puccha_start":
            puccha[0] if puccha else None,
        "bhadra_puccha_end":
            puccha[1] if puccha else None,
        "bhadra_mukha_start":
            mukha[0] if mukha else None,
        "bhadra_mukha_end":
            mukha[1] if mukha else None,
        "hindu_midnight":
            hindu_midnight,
    }


# ============================================================
# DISPLAY
# ============================================================

def print_result(result: dict):

    print()
    print("=" * 72)
    print("HOLIKA DAHAN")
    print("=" * 72)

    print(
        f"Date                 : {result['date']}"
    )

    print(
        f"Purnima Start        : "
        f"{format_dt(result['purnima_start'])}"
    )

    print(
        f"Purnima End          : "
        f"{format_dt(result['purnima_end'])}"
    )

    print(
        f"Pradosh Start        : "
        f"{format_dt(result['pradosh_start'])}"
    )

    print(
        f"Pradosh End          : "
        f"{format_dt(result['pradosh_end'])}"
    )

    print(
        f"Hindu Midnight       : "
        f"{format_dt(result['hindu_midnight'])}"
    )

    print(
        f"Rule                 : "
        f"{result['holika_rule']}"
    )

    print(
        f"Holika Dahan Start   : "
        f"{format_dt(result['holika_start'])}"
    )

    if result.get("holika_end") is not None:

        print(
            f"Holika Dahan End     : "
            f"{format_dt(result['holika_end'])}"
        )

    if result.get("bhadra_start") is not None:

        print(
            f"Bhadra Start         : "
            f"{format_dt(result['bhadra_start'])}"
        )

    if result.get("bhadra_end") is not None:

        print(
            f"Bhadra End           : "
            f"{format_dt(result['bhadra_end'])}"
        )

    if result.get("bhadra_puccha_start") is not None:

        print(
            f"Bhadra Puccha Start  : "
            f"{format_dt(result['bhadra_puccha_start'])}"
        )

        print(
            f"Bhadra Puccha End    : "
            f"{format_dt(result['bhadra_puccha_end'])}"
        )

    if result.get("bhadra_mukha_start") is not None:

        print(
            f"Bhadra Mukha Start   : "
            f"{format_dt(result['bhadra_mukha_start'])}"
        )

        print(
            f"Bhadra Mukha End     : "
            f"{format_dt(result['bhadra_mukha_end'])}"
        )

    print("=" * 72)


# ============================================================
# MAIN
# ============================================================

def main():

    conn = get_connection()

    try:

        # ----------------------------------------------------
        # Test all requested years.
        # ----------------------------------------------------

        for year in range(2025, 2028):

            print()
            print(
                f"\nSearching Holika Dahan for {year}..."
            )

            candidates = find_holika_candidates(
                conn,
                year,
            )

            if not candidates:

                print(
                    f"No Phalguna Purnima/Pradosh "
                    f"candidate found for {year}."
                )

                continue

            # Normally there should be exactly one.
            # Process each if the database produces more.
            for candidate in candidates:

                result = determine_holika_dahan(
                    conn,
                    candidate,
                )

                print_result(result)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
