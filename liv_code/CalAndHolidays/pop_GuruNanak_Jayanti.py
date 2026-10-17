#!/usr/bin/env python3

import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"
TIMEZONE = ZoneInfo("Asia/Kolkata")

KARTIKA_MASA = "08"
PURNIMA_TITHI = "15"
PAKSHA = "Shukla"


# ============================================================
# DATABASE
# ============================================================

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()


# ============================================================
# DATE / TIME HELPERS
# ============================================================

def parse_local(value, date=None):
    """
    Parse either:

    Full ISO datetime:
        2026-11-23T04:25:31.123456+05:30

    Or time-only:
        05:35:24
        05:35:24.123456
        05:35
    """

    if value is None:
        raise ValueError("Cannot parse None as datetime")

    value = value.strip()

    # Full datetime
    if "T" in value or " " in value:
        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TIMEZONE)
        else:
            dt = dt.astimezone(TIMEZONE)

        return dt

    # Time-only value
    if date is None:
        raise ValueError(
            f"Date required for time-only value: {value}"
        )

    if isinstance(date, datetime):
        date = date.date()
    elif isinstance(date, str):
        date = datetime.strptime(date, "%Y-%m-%d").date()

    for fmt in ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M"):
        try:
            time_value = datetime.strptime(value, fmt).time()

            return datetime.combine(
                date,
                time_value
            ).replace(tzinfo=TIMEZONE)

        except ValueError:
            continue

    raise ValueError(
        f"Unsupported time/datetime format: {value}"
    )


def format_local(dt):
    """Return timezone-aware ISO 8601 local datetime."""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)
    else:
        dt = dt.astimezone(TIMEZONE)

    return dt.isoformat()


# ============================================================
# FIND KARTIKA MASA INTERVAL
# ============================================================

def get_kartika_start(year):
    """
    Find the beginning of Kartika Masa for the Gregorian year.

    We use the Masa_Transition table because it gives the
    exact astronomical Masa transition.
    """

    rows = cur.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Masa_Number,
            Masa_English,
            Masa_Hindi,
            Masa_Type
        FROM Masa_Transition
        WHERE Location = ?
          AND Masa_Number = ?
        ORDER BY Start_Date_Time_Local
        """,
        (
            LOCATION,
            KARTIKA_MASA
        )
    ).fetchall()

    candidates = []

    for row in rows:

        start = parse_local(row["Start_Date_Time_Local"])
        end = parse_local(row["End_Date_Time_Local"])

        # Kartika that begins in the requested Gregorian year.
        if start.year == year:
            candidates.append(
                {
                    "start": start,
                    "end": end,
                    "masa_type": row["Masa_Type"],
                    "masa_english": row["Masa_English"],
                    "masa_hindi": row["Masa_Hindi"]
                }
            )

    if not candidates:
        raise RuntimeError(
            f"Kartika Masa beginning in {year} was not found."
        )

    candidates.sort(key=lambda x: x["start"])

    return candidates[0]

# ============================================================
# FIND PURNIMA CANDIDATES
# ============================================================

def get_purnima_candidates(kartika_start):
    """
    Find Shukla Purnima transitions approximately halfway
    through Kartika Masa.

    Kartika Shukla Purnima normally occurs about 14-16 days
    after the beginning of Kartika.

    We use a broad 10-day to 20-day window to safely cover
    variations in the lunar month.
    """

    window_start = kartika_start + timedelta(days=10)
    window_end = kartika_start + timedelta(days=20)

    rows = cur.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Tithi,
            Paksha
        FROM Tithi_Transition
        WHERE Location = ?
          AND Tithi = ?
          AND Paksha = ?
        ORDER BY Start_Date_Time_Local
        """,
        (
            LOCATION,
            PURNIMA_TITHI,
            PAKSHA
        )
    ).fetchall()

    candidates = []

    for row in rows:

        start = parse_local(row["Start_Date_Time_Local"])
        end = parse_local(row["End_Date_Time_Local"])

        # Candidate must overlap our Kartika-Purnima window.
        if end < window_start:
            continue

        if start > window_end:
            continue

        # Calculate distance from the expected middle of
        # Kartika.
        midpoint = kartika_start + timedelta(days=15)

        if start <= midpoint <= end:
            distance = timedelta(0)
        elif end < midpoint:
            distance = midpoint - end
        else:
            distance = start - midpoint

        candidates.append(
            {
                "start": start,
                "end": end,
                "distance": distance
            }
        )

    return candidates

# ============================================================
# SELECT KARTIKA SHUKLA PURNIMA
# ============================================================

def select_kartika_purnima(kartika_start):

    candidates = get_purnima_candidates(kartika_start)

    if not candidates:
        raise RuntimeError(
            "No Shukla Purnima transition found "
            f"10-20 days after Kartika Masa start: "
            f"{kartika_start}"
        )

    candidates.sort(
        key=lambda x: (
            x["distance"],
            x["start"]
        )
    )

    return candidates[0]

# ============================================================
# POPULATE ONE YEAR
# ============================================================

def populate_year(year):

    kartika = get_kartika_start(year)

    kartika_start = kartika["start"]
    kartika_end = kartika["end"]

    purnima = select_kartika_purnima(kartika_start)

    festival_date = purnima["start"].date()

    date_string = festival_date.isoformat()

    cur.execute(
        """
        INSERT OR REPLACE INTO Guru_Nanak_Jayanti (
            Date,
            Location,
            Purnima_Start_Local,
            Purnima_End_Local
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            date_string,
            LOCATION,
            format_local(purnima["start"]),
            format_local(purnima["end"])
        )
    )

    print()
    print(f"Gregorian Year : {year}")
    print(
        f"Kartika Masa   : "
        f"{format_local(kartika_start)} -> "
        f"{format_local(kartika_end)}"
    )
    print(
        f"Purnima        : "
        f"{format_local(purnima['start'])} -> "
        f"{format_local(purnima['end'])}"
    )
    print(
        f"Guru Nanak Jayanti : {date_string}"
    )

# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # Change these two values as required.
    # --------------------------------------------------------

    START_YEAR = 1927
    END_YEAR = 2125

    # --------------------------------------------------------
    # Create table if it does not already exist.
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS Guru_Nanak_Jayanti (
            Date TEXT NOT NULL,
            Location TEXT NOT NULL,
            Purnima_Start_Local TEXT NOT NULL,
            Purnima_End_Local TEXT NOT NULL,
            PRIMARY KEY (Date, Location)
        )
        """
    )

    # --------------------------------------------------------
    # Populate years
    # --------------------------------------------------------

    for year in range(START_YEAR, END_YEAR + 1):

        try:
            populate_year(year)

        except Exception as e:
            print()
            print(
                f"{year}: ERROR: {e}"
            )

    conn.commit()
    conn.close()

    print()
    print("=" * 60)
    print("Guru Nanak Jayanti population completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
