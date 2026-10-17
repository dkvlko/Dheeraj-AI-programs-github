#!/usr/bin/env python3

import sqlite3
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"

START_YEAR = 1927
END_YEAR = 2125

TIMEZONE = ZoneInfo("Asia/Kolkata")


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def parse_local_datetime(value):
    """
    Parse a datetime stored in the database.

    Handles both:
        1976-08-09 05:37:22
    and:
        1976-08-09T05:37:22+05:30
    """
    if value is None:
        return None

    value = value.strip()

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise RuntimeError(f"Unable to parse datetime: {value}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)

    return dt.astimezone(TIMEZONE)


def local_date_from_datetime(value):
    return parse_local_datetime(value).date()


def format_local_datetime(dt):
    return dt.astimezone(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# TABLE CREATION
# ============================================================

def create_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Raksha_Bandhan (
            Date TEXT NOT NULL,
            Location TEXT NOT NULL,
            Purnima_Start_Local TEXT NOT NULL,
            Purnima_End_Local TEXT NOT NULL,
            Bhadra_Start_Local TEXT,
            Bhadra_End_Local TEXT,
            Bhadra_Puccha_Start_Local TEXT,
            Bhadra_Puccha_End_Local TEXT,
            Rule_Applied TEXT NOT NULL,
            PRIMARY KEY (Date, Location)
        )
    """)


# ============================================================
# MASA
# ============================================================

def get_shravana_number(conn):
    """
    Determine the Masa.Number corresponding to Shravana.

    SanskritName is checked first because it is the most
    unambiguous field in the user's Masa table.
    """

    row = conn.execute("""
        SELECT Number
        FROM Masa
        WHERE SanskritName = 'श्रावण'
           OR Name = 'Shravana'
           OR Name = 'Shravan'
        ORDER BY
            CASE
                WHEN SanskritName = 'श्रावण' THEN 1
                WHEN Name = 'Shravana' THEN 2
                ELSE 3
            END
        LIMIT 1
    """).fetchone()

    if row is None:
        raise RuntimeError(
            "Unable to determine Masa.Number for Shravana."
        )

    return row[0]


# ============================================================
# HINDU CALENDAR -- AUTHORITATIVE MASA INFORMATION
# ============================================================

def get_shravana_period_from_hindu_calendar(conn, year, shravana_number):
    """
    Find the Gregorian dates on which Hindu_Calendar assigns
    Masa = Shravana.

    We deliberately DO NOT require Tithi = 15 here.

    This is important because a Purnima can be a Kshaya tithi
    and therefore may not appear as Tithi='15' on any sunrise
    row in Hindu_Calendar.
    """

    rows = conn.execute("""
        SELECT
            Year,
            Month,
            Date,
            Tithi,
            Paksha,
            Masa,
            Adhika_Masa
        FROM Hindu_Calendar
        WHERE Year = ?
          AND Masa = ?
          AND Adhika_Masa = 0
        ORDER BY Month, Date
    """, (str(year), shravana_number)).fetchall()

    if not rows:
        return None

    first = date(
        int(rows[0][0]),
        int(rows[0][1]),
        int(rows[0][2])
    )

    last = date(
        int(rows[-1][0]),
        int(rows[-1][1]),
        int(rows[-1][2])
    )

    return first, last


# ============================================================
# MASA TRANSITION -- AUTHORITATIVE LUNAR MONTH BOUNDARY
# ============================================================

def get_shravana_transition(conn, year, shravana_number):
    """
    Find the Masa_Transition interval for normal Shravana.

    This is used to locate the actual astronomical month interval,
    particularly when Hindu_Calendar has no sunrise Purnima row.
    """

    row = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local
        FROM Masa_Transition
        WHERE Location = ?
          AND Masa_Number = ?
          AND Masa_Type = 'Normal'
          AND Start_Date_Time_Local < ?
          AND End_Date_Time_Local >= ?
        ORDER BY Start_Date_Time_Local
        LIMIT 1
    """, (
        LOCATION,
        shravana_number,
        f"{year + 1:04d}-01-01",
        f"{year - 1:04d}-01-01"
    )).fetchone()

    if row is None:
        raise RuntimeError(
            f"No normal Shravana Masa_Transition found for {year}"
        )

    return (
        parse_local_datetime(row[0]),
        parse_local_datetime(row[1])
    )


# ============================================================
# TITHI TRANSITION -- FIND ACTUAL SHUKLA PURNIMA
# ============================================================

def get_shukla_purnima_transition(
    conn,
    masa_start,
    masa_end
):
    """
    Find the Shukla Purnima transition that belongs to Shravana.

    We query Tithi_Transition directly.

    This is essential for cases such as 1976, where:

        Shukla 14:
            Aug 08 06:27:16 -> Aug 09 05:37:22

        Shukla 15:
            Aug 09 05:37:22 -> Aug 10 05:13:29

        Krishna 01:
            Aug 10 05:13:29 -> Aug 11 05:20:22

    The Purnima never occurs at sunrise, so Hindu_Calendar
    contains no Tithi='15' row.
    """

    rows = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Tithi,
            Paksha
        FROM Tithi_Transition
        WHERE Location = ?
          AND Tithi = '15'
          AND Paksha = 'Shukla'
          AND Start_Date_Time_Local < ?
          AND End_Date_Time_Local > ?
        ORDER BY Start_Date_Time_Local
    """, (
        LOCATION,
        format_local_datetime(masa_end),
        format_local_datetime(masa_start)
    )).fetchall()

    if not rows:
        return None

    candidates = []

    for row in rows:
        start = parse_local_datetime(row[0])
        end = parse_local_datetime(row[1])

        # Purnima must overlap the Shravana interval.
        overlap_start = max(start, masa_start)
        overlap_end = min(end, masa_end)

        if overlap_start < overlap_end:
            candidates.append((start, end))

    if not candidates:
        return None

    # There should normally be exactly one.
    # Choose the one whose interval has the greatest overlap.
    candidates.sort(
        key=lambda x: (
            min(x[1], masa_end) - max(x[0], masa_start)
        ),
        reverse=True
    )

    return candidates[0]


# ============================================================
# BHADRA
# ============================================================

def get_bhadra_segments(conn, purnima_start, purnima_end):
    """
    Return every Bhadra-related segment overlapping Purnima.

    We deliberately include:
        Bhadra
        Bhadra_Puccha
        Bhadra_Mukha

    because Puccha and Mukha are subdivisions of the overall
    Bhadra interval.

    They must NOT be treated as gaps when deciding whether
    Bhadra completely occupies Purnima.
    """

    rows = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Bhadra_Type
        FROM Bhadra_Transition
        WHERE Location = ?
          AND Start_Date_Time_Local < ?
          AND End_Date_Time_Local > ?
        ORDER BY Start_Date_Time_Local
    """, (
        LOCATION,
        format_local_datetime(purnima_end),
        format_local_datetime(purnima_start)
    )).fetchall()

    segments = []

    for row in rows:
        start = parse_local_datetime(row[0])
        end = parse_local_datetime(row[1])
        bhadra_type = row[2]

        overlap_start = max(start, purnima_start)
        overlap_end = min(end, purnima_end)

        if overlap_start < overlap_end:
            segments.append({
                "start": start,
                "end": end,
                "overlap_start": overlap_start,
                "overlap_end": overlap_end,
                "type": bhadra_type
            })

    return segments


# ============================================================
# MERGE INTERVALS
# ============================================================

def merge_intervals(intervals):
    """
    Merge overlapping or directly adjacent datetime intervals.
    """

    if not intervals:
        return []

    intervals = sorted(intervals, key=lambda x: x[0])

    merged = [list(intervals[0])]

    for start, end in intervals[1:]:
        current = merged[-1]

        if start <= current[1]:
            if end > current[1]:
                current[1] = end
        else:
            merged.append([start, end])

    return [
        (start, end)
        for start, end in merged
    ]


def bhadra_completely_covers_purnima(
    purnima_start,
    purnima_end,
    bhadra_segments
):
    """
    Determine whether the entire Purnima interval is covered by
    Bhadra-related segments.

    Bhadra_Puccha and Bhadra_Mukha are included as part of the
    continuous Bhadra interval.
    """

    if not bhadra_segments:
        return False

    intervals = []

    for segment in bhadra_segments:
        intervals.append((
            max(segment["start"], purnima_start),
            min(segment["end"], purnima_end)
        ))

    merged = merge_intervals(intervals)

    if not merged:
        return False

    cursor = purnima_start

    for start, end in merged:

        if start > cursor:
            # There is a gap.
            return False

        if end > cursor:
            cursor = end

        if cursor >= purnima_end:
            return True

    return False


# ============================================================
# FIND PUCCHA
# ============================================================

def get_puccha_segments(
    bhadra_segments,
    purnima_start,
    purnima_end
):
    """
    Return Bhadra_Puccha portions overlapping Purnima.
    """

    result = []

    for segment in bhadra_segments:

        if segment["type"] != "Bhadra_Puccha":
            continue

        start = max(
            segment["start"],
            purnima_start
        )

        end = min(
            segment["end"],
            purnima_end
        )

        if start < end:
            result.append((start, end))

    return result


# ============================================================
# CHOOSE RAKSHA BANDHAN DATE
# ============================================================

def determine_raksha_bandhan_date(
    purnima_start,
    purnima_end,
    bhadra_segments
):
    """
    Apply the user's specified rule.

    RULE:

    1. If Bhadra does not completely occupy Purnima:
           declare the Purnima date.

    2. If Bhadra completely occupies Purnima:
           a. If Bhadra Puccha exists:
                  declare the date containing Puccha.
           b. If no Puccha exists:
                  ignore Bhadra and declare the Purnima date.
    """

    completely_covered = bhadra_completely_covers_purnima(
        purnima_start,
        purnima_end,
        bhadra_segments
    )

    puccha_segments = get_puccha_segments(
        bhadra_segments,
        purnima_start,
        purnima_end
    )

    if completely_covered:

        if puccha_segments:

            # Use the first Puccha occurrence.
            puccha_start, puccha_end = puccha_segments[0]

            raksha_date = puccha_start.date()

            rule = (
                "Bhadra completely occupies Purnima; "
                "Bhadra Puccha exists; "
                "Puccha date selected"
            )

            return (
                raksha_date,
                puccha_start,
                puccha_end,
                rule
            )

        else:

            raksha_date = purnima_start.date()

            rule = (
                "Bhadra completely occupies Purnima; "
                "no Bhadra Puccha; "
                "Bhadra ignored and Purnima date selected"
            )

            return (
                raksha_date,
                None,
                None,
                rule
            )

    # Normal case:
    #
    # Purnima is not completely occupied by Bhadra.
    #
    # The Purnima civil date is used.
    raksha_date = purnima_start.date()

    rule = (
        "Bhadra does not completely occupy Purnima; "
        "Purnima date selected"
    )

    return (
        raksha_date,
        None,
        None,
        rule
    )


# ============================================================
# INSERT RESULT
# ============================================================

def insert_result(
    conn,
    raksha_date,
    purnima_start,
    purnima_end,
    bhadra_segments,
    puccha_start,
    puccha_end,
    rule
):
    """
    Store one Raksha Bandhan result.
    """

    # Overall Bhadra interval.
    #
    # We combine all Bhadra-related segments into one continuous
    # interval for storage.
    if bhadra_segments:

        bhadra_intervals = [
            (x["start"], x["end"])
            for x in bhadra_segments
        ]

        merged = merge_intervals(bhadra_intervals)

        if merged:
            bhadra_start = merged[0][0]
            bhadra_end = merged[-1][1]
        else:
            bhadra_start = None
            bhadra_end = None

    else:
        bhadra_start = None
        bhadra_end = None

    conn.execute("""
        INSERT OR REPLACE INTO Raksha_Bandhan (
            Date,
            Location,
            Purnima_Start_Local,
            Purnima_End_Local,
            Bhadra_Start_Local,
            Bhadra_End_Local,
            Bhadra_Puccha_Start_Local,
            Bhadra_Puccha_End_Local,
            Rule_Applied
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        raksha_date.isoformat(),
        LOCATION,
        format_local_datetime(purnima_start),
        format_local_datetime(purnima_end),
        (
            format_local_datetime(bhadra_start)
            if bhadra_start else None
        ),
        (
            format_local_datetime(bhadra_end)
            if bhadra_end else None
        ),
        (
            format_local_datetime(puccha_start)
            if puccha_start else None
        ),
        (
            format_local_datetime(puccha_end)
            if puccha_end else None
        ),
        rule
    ))


# ============================================================
# PROCESS ONE YEAR
# ============================================================

def process_year(year):
    """
    Process one Gregorian year in an independent transaction.

    If this year fails, only this year's transaction is rolled
    back. Previously committed years remain intact.
    """

    conn = get_connection()

    try:

        print()
        print("=" * 70)
        print(f"PROCESSING RAKSHA BANDHAN {year}")
        print("=" * 70)

        create_table(conn)

        # ----------------------------------------------------
        # Determine Shravana number.
        # ----------------------------------------------------

        shravana_number = get_shravana_number(conn)

        print(
            f"Shravana Masa Number: {shravana_number}"
        )

        # ----------------------------------------------------
        # Authoritative Hindu_Calendar Shravana period.
        # ----------------------------------------------------

        hc_period = get_shravana_period_from_hindu_calendar(
            conn,
            year,
            shravana_number
        )

        if hc_period is None:
            raise RuntimeError(
                f"No normal Shravana rows found in "
                f"Hindu_Calendar for {year}"
            )

        hc_start, hc_end = hc_period

        print(
            f"Hindu_Calendar Shravana rows: "
            f"{hc_start} -> {hc_end}"
        )

        # ----------------------------------------------------
        # Masa_Transition Shravana interval.
        # ----------------------------------------------------

        masa_start, masa_end = get_shravana_transition(
            conn,
            year,
            shravana_number
        )

        print(
            "Masa_Transition Shravana: "
            f"{format_local_datetime(masa_start)} -> "
            f"{format_local_datetime(masa_end)}"
        )

        # ----------------------------------------------------
        # Actual Shukla Purnima transition.
        # ----------------------------------------------------

        purnima = get_shukla_purnima_transition(
            conn,
            masa_start,
            masa_end
        )

        if purnima is None:
            raise RuntimeError(
                f"No Shravana Shukla Purnima transition "
                f"found for {year}"
            )

        purnima_start, purnima_end = purnima

        print(
            "Shukla Purnima: "
            f"{format_local_datetime(purnima_start)} -> "
            f"{format_local_datetime(purnima_end)}"
        )

        # ----------------------------------------------------
        # Bhadra.
        # ----------------------------------------------------

        bhadra_segments = get_bhadra_segments(
            conn,
            purnima_start,
            purnima_end
        )

        if bhadra_segments:

            print("Bhadra-related segments:")

            for segment in bhadra_segments:
                print(
                    f"  {segment['type']}: "
                    f"{format_local_datetime(segment['start'])} -> "
                    f"{format_local_datetime(segment['end'])}"
                )

        else:
            print("No Bhadra overlap with Purnima.")

        # ----------------------------------------------------
        # Apply user's rule.
        # ----------------------------------------------------

        (
            raksha_date,
            puccha_start,
            puccha_end,
            rule
        ) = determine_raksha_bandhan_date(
            purnima_start,
            purnima_end,
            bhadra_segments
        )

        print()
        print(
            f"Raksha Bandhan Date: {raksha_date}"
        )
        print(f"Rule: {rule}")

        if puccha_start:
            print(
                "Selected Puccha: "
                f"{format_local_datetime(puccha_start)} -> "
                f"{format_local_datetime(puccha_end)}"
            )

        # ----------------------------------------------------
        # Store result.
        # ----------------------------------------------------

        insert_result(
            conn,
            raksha_date,
            purnima_start,
            purnima_end,
            bhadra_segments,
            puccha_start,
            puccha_end,
            rule
        )

        # ----------------------------------------------------
        # Commit this year.
        # ----------------------------------------------------

        conn.commit()

        print()
        print(f"COMMITTED {year}")

    except Exception:

        conn.rollback()

        print()
        print(
            f"ERROR processing {year}; "
            f"transaction rolled back."
        )

        raise

    finally:
        conn.close()


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("RAKSHA BANDHAN POPULATION")
    print("=" * 70)
    print(f"Database : {DB_PATH}")
    print(f"Location : {LOCATION}")
    print(f"Years    : {START_YEAR}-{END_YEAR}")
    print("=" * 70)

    for year in range(START_YEAR, END_YEAR + 1):
        process_year(year)

    print()
    print("=" * 70)
    print("RAKSHA BANDHAN POPULATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
