#!/usr/bin/env python3

import sqlite3
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"
LATITUDE = 26.8467
LONGITUDE = 80.9462
TIMEZONE = ZoneInfo("Asia/Kolkata")

START_YEAR = 1927
END_YEAR = 2125

# IMPORTANT:
# Verify this against your database if necessary.
# In your existing convention:
# Jyeshtha     = 03
# Bhadrapada   = 06
# Therefore Kartik = 08
KARTIK_MASA = "08"

PURNIMA_TITHI = "15"
SHUKLA_PAKSHA = "Shukla"


# ============================================================
# TABLE CREATION
# ============================================================

def create_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Karthi_Purnima (
            Date TEXT NOT NULL,
            Location TEXT NOT NULL,
            Purnima_Start_Local TEXT,
            Purnima_End_Local TEXT,
            Rule_Applied TEXT NOT NULL,
            PRIMARY KEY (Date, Location)
        )
    """)


# ============================================================
# DATE/TIME PARSING
# ============================================================

def parse_local(value, date_value=None):
    """
    Parse values from local-date/time columns.

    Handles:
        YYYY-MM-DD HH:MM:SS
        YYYY-MM-DD HH:MM:SS+05:30
        YYYY-MM-DDTHH:MM:SS
        HH:MM:SS
        HH:MM
    """

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    # --------------------------------------------------------
    # Full ISO datetime
    # --------------------------------------------------------
    try:
        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TIMEZONE)
        else:
            dt = dt.astimezone(TIMEZONE)

        return dt

    except ValueError:
        pass

    # --------------------------------------------------------
    # Time-only value
    # --------------------------------------------------------
    if date_value is not None:

        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                t = datetime.strptime(value, fmt).time()

                dt = datetime.combine(
                    date_value,
                    t,
                    tzinfo=TIMEZONE
                )

                return dt

            except ValueError:
                continue

    return None


def parse_transition_datetime(value):
    """
    Parse transition datetime.

    Transition tables normally contain complete timestamps.
    The result is always converted to Asia/Kolkata.
    """

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    try:
        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TIMEZONE)
        else:
            dt = dt.astimezone(TIMEZONE)

        return dt

    except ValueError as exc:
        raise ValueError(
            f"Cannot parse transition datetime: {value}"
        ) from exc


# ============================================================
# SUNRISE
# ============================================================

def get_sunrise(conn, gregorian_date):
    """
    Read sunrise from Sun_Position.

    Sunrise_Time may be stored as a time-only value,
    so the Gregorian date is explicitly attached.
    """

    row = conn.execute("""
        SELECT Sunrise_Time
        FROM Sun_Position
        WHERE Date = ?
          AND Location = ?
        LIMIT 1
    """, (
        gregorian_date.isoformat(),
        LOCATION
    )).fetchone()

    if not row:
        return None

    return parse_local(
        row[0],
        gregorian_date
    )


# ============================================================
# CHECK WHETHER AN INTERVAL CONTAINS SUNRISE
# ============================================================

def interval_contains(moment, start_dt, end_dt):
    """
    True when moment lies inside [start_dt, end_dt).
    """

    if start_dt is None or end_dt is None:
        return False

    return start_dt <= moment < end_dt


# ============================================================
# PRIMARY METHOD
# Purnimanta_Tithi_Transition
# ============================================================

def find_from_purnimanta_transition(conn, year):
    """
    Primary source.

    Find Kartik Shukla Purnima in
    Purnimanta_Tithi_Transition and select the interval
    that prevails at sunrise.
    """

    rows = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Tithi,
            Paksha,
            Masa,
            Masa_Type
        FROM Purnimanta_Tithi_Transition
        WHERE Location = ?
          AND Tithi = ?
          AND Paksha = ?
          AND Masa = ?
          AND (
                Start_Date_Time_Local LIKE ?
             OR End_Date_Time_Local LIKE ?
             OR Start_Date_Time_Local LIKE ?
             OR End_Date_Time_Local LIKE ?
          )
        ORDER BY Start_Date_Time_Local
    """, (
        LOCATION,
        PURNIMA_TITHI,
        SHUKLA_PAKSHA,
        KARTIK_MASA,
        f"{year}-%",
        f"{year}-%",
        f"{year + 1}-%",
        f"{year + 1}-%",
    )).fetchall()

    if not rows:
        raise LookupError(
            f"No Kartik Shukla Purnima found in "
            f"Purnimanta_Tithi_Transition for {year}"
        )

    # --------------------------------------------------------
    # Examine every candidate.
    #
    # This is important because more than one interval may
    # occur near a calendar year boundary.
    # --------------------------------------------------------

    candidates = []

    for row in rows:

        start = parse_transition_datetime(row[0])
        end = parse_transition_datetime(row[1])

        if start is None or end is None:
            continue

        # Candidate Gregorian dates on which sunrise can
        # occur while this Purnima is active.
        current_date = start.date()

        while current_date <= end.date():

            sunrise = get_sunrise(
                conn,
                current_date
            )

            if sunrise and interval_contains(
                sunrise,
                start,
                end
            ):
                candidates.append({
                    "date": current_date,
                    "start": start,
                    "end": end,
                    "rule": (
                        "Purnimanta_Tithi_Transition: "
                        "Kartik Shukla Purnima prevailing at sunrise"
                    )
                })

            current_date += timedelta(days=1)

    # --------------------------------------------------------
    # Prefer candidate belonging to requested year.
    # --------------------------------------------------------

    candidates = [
        c for c in candidates
        if c["date"].year == year
    ]

    if not candidates:
        raise LookupError(
            f"Kartik Shukla Purnima transition found for {year}, "
            f"but none prevailed at sunrise in that Gregorian year"
        )

    # Normally exactly one candidate exists.
    # If multiple exist, use the earliest sunrise-valid date.
    candidates.sort(key=lambda x: x["date"])

    return candidates[0]


# ============================================================
# FIRST FALLBACK
# Hindu_Calendar
# ============================================================

def find_from_hindu_calendar(conn, year):
    """
    First fallback.

    Directly locate Kartik Shukla Purnima in Hindu_Calendar.

    We do NOT blindly assume that the first row is correct.
    If several rows exist, sunrise is used where possible.
    """

    rows = conn.execute("""
        SELECT
            Date,
            Masa,
            Paksha,
            Tithi
        FROM Hindu_Calendar
        WHERE Location = ?
          AND Masa = ?
          AND Paksha = ?
          AND Tithi = ?
          AND Date >= ?
          AND Date < ?
        ORDER BY Date
    """, (
        LOCATION,
        KARTIK_MASA,
        SHUKLA_PAKSHA,
        PURNIMA_TITHI,
        f"{year}-01-01",
        f"{year + 1}-01-01"
    )).fetchall()

    if not rows:
        raise LookupError(
            f"No Kartik Shukla Purnima row in "
            f"Hindu_Calendar for {year}"
        )

    candidates = []

    for row in rows:

        try:
            d = date.fromisoformat(str(row[0])[:10])
        except ValueError:
            continue

        sunrise = get_sunrise(conn, d)

        candidates.append({
            "date": d,
            "start": None,
            "end": None,
            "sunrise": sunrise,
            "rule": (
                "Hindu_Calendar: "
                "Kartik Shukla Purnima"
            )
        })

    if not candidates:
        raise LookupError(
            f"Hindu_Calendar contained unusable "
            f"Kartik Purnima data for {year}"
        )

    # If multiple rows exist, prefer the one for which
    # sunrise data exists.
    with_sunrise = [
        c for c in candidates
        if c["sunrise"] is not None
    ]

    if with_sunrise:
        candidates = with_sunrise

    candidates.sort(key=lambda x: x["date"])

    result = candidates[0]

    return {
        "date": result["date"],
        "start": None,
        "end": None,
        "rule": result["rule"]
    }


# ============================================================
# SECOND FALLBACK
# Tithi_Transition
# ============================================================

def find_from_tithi_transition(conn, year):
    """
    Second fallback.

    Use the fundamental Tithi_Transition table.

    Tithi_Transition does not contain Masa, so we use the
    Kartik period from Masa_Transition to restrict the
    candidates.

    We then determine which Purnima interval prevails
    at sunrise.
    """

    # --------------------------------------------------------
    # Get Kartik Masa transition intervals.
    #
    # We use LIKE on the local datetime because the exact
    # column formatting can vary slightly.
    # --------------------------------------------------------

    masa_rows = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Masa,
            Masa_Type
        FROM Masa_Transition
        WHERE Location = ?
          AND Masa = ?
          AND (
                Start_Date_Time_Local LIKE ?
             OR End_Date_Time_Local LIKE ?
             OR Start_Date_Time_Local LIKE ?
             OR End_Date_Time_Local LIKE ?
          )
        ORDER BY Start_Date_Time_Local
    """, (
        LOCATION,
        KARTIK_MASA,
        f"{year}-%",
        f"{year}-%",
        f"{year + 1}-%",
        f"{year + 1}-%",
    )).fetchall()

    # --------------------------------------------------------
    # If Masa_Transition does not provide Kartik, we cannot
    # safely infer Kartik from Tithi_Transition alone.
    # --------------------------------------------------------

    if not masa_rows:
        raise LookupError(
            f"No Kartik Masa_Transition interval found "
            f"for {year}"
        )

    masa_intervals = []

    for row in masa_rows:

        start = parse_transition_datetime(row[0])
        end = parse_transition_datetime(row[1])

        if start and end:
            masa_intervals.append((start, end))

    if not masa_intervals:
        raise LookupError(
            f"Kartik Masa_Transition intervals for {year} "
            f"could not be parsed"
        )

    # --------------------------------------------------------
    # Find all Shukla Purnima tithi intervals.
    # --------------------------------------------------------

    tithi_rows = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Tithi,
            Paksha
        FROM Tithi_Transition
        WHERE Location = ?
          AND Tithi = ?
          AND Paksha = ?
          AND (
                Start_Date_Time_Local LIKE ?
             OR End_Date_Time_Local LIKE ?
             OR Start_Date_Time_Local LIKE ?
             OR End_Date_Time_Local LIKE ?
          )
        ORDER BY Start_Date_Time_Local
    """, (
        LOCATION,
        PURNIMA_TITHI,
        SHUKLA_PAKSHA,
        f"{year}-%",
        f"{year}-%",
        f"{year + 1}-%",
        f"{year + 1}-%",
    )).fetchall()

    if not tithi_rows:
        raise LookupError(
            f"No Shukla Purnima Tithi_Transition "
            f"interval found for {year}"
        )

    candidates = []

    for row in tithi_rows:

        start = parse_transition_datetime(row[0])
        end = parse_transition_datetime(row[1])

        if not start or not end:
            continue

        # ----------------------------------------------------
        # The Tithi interval must overlap Kartik.
        # ----------------------------------------------------

        overlaps_kartik = any(
            start < masa_end and end > masa_start
            for masa_start, masa_end in masa_intervals
        )

        if not overlaps_kartik:
            continue

        # ----------------------------------------------------
        # Determine the Gregorian date on which this Purnima
        # prevails at sunrise.
        # ----------------------------------------------------

        current_date = start.date()

        while current_date <= end.date():

            if current_date.year != year:
                current_date += timedelta(days=1)
                continue

            sunrise = get_sunrise(
                conn,
                current_date
            )

            if sunrise and interval_contains(
                sunrise,
                start,
                end
            ):
                candidates.append({
                    "date": current_date,
                    "start": start,
                    "end": end,
                    "rule": (
                        "Tithi_Transition fallback: "
                        "Kartik Masa_Transition + "
                        "Shukla Purnima prevailing at sunrise"
                    )
                })

            current_date += timedelta(days=1)

    if not candidates:
        raise LookupError(
            f"Tithi_Transition contained Shukla Purnima "
            f"for {year}, but no Kartik Purnima prevailed "
            f"at sunrise"
        )

    candidates.sort(key=lambda x: x["date"])

    return candidates[0]


# ============================================================
# RESILIENT FINDER
# ============================================================

def find_karthik_purnima(conn, year):

    # --------------------------------------------------------
    # LEVEL 1
    # --------------------------------------------------------

    try:
        result = find_from_purnimanta_transition(
            conn,
            year
        )

        print(
            f"  {year}: PRIMARY -> "
            f"{result['date']} "
            f"({result['rule']})"
        )

        return result

    except Exception as exc:
        print(
            f"  {year}: Primary failed: {exc}"
        )

    # --------------------------------------------------------
    # LEVEL 2
    # --------------------------------------------------------

    try:
        result = find_from_hindu_calendar(
            conn,
            year
        )

        print(
            f"  {year}: FALLBACK-1 -> "
            f"{result['date']} "
            f"({result['rule']})"
        )

        return result

    except Exception as exc:
        print(
            f"  {year}: Hindu_Calendar fallback failed: "
            f"{exc}"
        )

    # --------------------------------------------------------
    # LEVEL 3
    # --------------------------------------------------------

    try:
        result = find_from_tithi_transition(
            conn,
            year
        )

        print(
            f"  {year}: FALLBACK-2 -> "
            f"{result['date']} "
            f"({result['rule']})"
        )

        return result

    except Exception as exc:
        print(
            f"  {year}: Tithi_Transition fallback failed: "
            f"{exc}"
        )

        raise RuntimeError(
            f"Unable to determine Karthik Purnima "
            f"for {year} using any existing table"
        ) from exc


# ============================================================
# WRITE ONE YEAR
# ============================================================

def populate_year(conn, year):

    print()
    print("=" * 60)
    print(f"Processing Karthik Purnima: {year}")
    print("=" * 60)

    # --------------------------------------------------------
    # IMPORTANT:
    # Calculation happens BEFORE BEGIN.
    #
    # Therefore an error during calculation does not affect
    # already committed years.
    # --------------------------------------------------------

    result = find_karthik_purnima(
        conn,
        year
    )

    event_date = result["date"]

    start_local = result.get("start")
    end_local = result.get("end")

    start_text = (
        start_local.isoformat()
        if start_local
        else None
    )

    end_text = (
        end_local.isoformat()
        if end_local
        else None
    )

    # --------------------------------------------------------
    # YEAR-WISE TRANSACTION
    # --------------------------------------------------------

    try:

        conn.execute("BEGIN")

        # Remove only this year's existing result.
        conn.execute("""
            DELETE FROM Karthi_Purnima
            WHERE Location = ?
              AND Date >= ?
              AND Date < ?
        """, (
            LOCATION,
            f"{year}-01-01",
            f"{year + 1}-01-01"
        ))

        conn.execute("""
            INSERT INTO Karthi_Purnima (
                Date,
                Location,
                Purnima_Start_Local,
                Purnima_End_Local,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            event_date.isoformat(),
            LOCATION,
            start_text,
            end_text,
            result["rule"]
        ))

        conn.commit()

        print(
            f"  COMMITTED {year}: "
            f"{event_date.isoformat()}"
        )

    except Exception:

        conn.rollback()

        print(
            f"  ROLLBACK {year}"
        )

        raise


# ============================================================
# VALIDATION
# ============================================================

def validate_results(conn):

    print()
    print("=" * 60)
    print("KARTHIK PURNIMA RESULTS")
    print("=" * 60)

    rows = conn.execute("""
        SELECT
            Date,
            Location,
            Purnima_Start_Local,
            Purnima_End_Local,
            Rule_Applied
        FROM Karthi_Purnima
        WHERE Location = ?
          AND Date >= ?
          AND Date <= ?
        ORDER BY Date
    """, (
        LOCATION,
        f"{START_YEAR}-01-01",
        f"{END_YEAR}-12-31"
    )).fetchall()

    for row in rows:
        print()
        print(f"Date       : {row[0]}")
        print(f"Location   : {row[1]}")
        print(f"Purnima    : {row[2]}")
        print(f"Ends       : {row[3]}")
        print(f"Rule       : {row[4]}")

    print()
    print(f"Total rows: {len(rows)}")


# ============================================================
# MAIN
# ============================================================

def main():

    conn = sqlite3.connect(
        DB_PATH,
        timeout=30
    )

    try:

        # ----------------------------------------------------
        # SQLite safety
        # ----------------------------------------------------

        conn.execute("PRAGMA foreign_keys = ON")

        create_table(conn)
        conn.commit()

        # ----------------------------------------------------
        # Process EACH YEAR independently.
        #
        # If 2026 fails, 2024 and 2025 remain committed.
        # ----------------------------------------------------

        for year in range(
            START_YEAR,
            END_YEAR + 1
        ):

            try:

                populate_year(
                    conn,
                    year
                )

            except Exception as exc:

                print()
                print(
                    f"ERROR processing {year}: {exc}"
                )

                # Continue with next year rather than
                # destroying previously committed results.
                continue

        validate_results(conn)

    finally:

        conn.close()


if __name__ == "__main__":
    main()
