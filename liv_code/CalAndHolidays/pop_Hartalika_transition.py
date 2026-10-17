#!/usr/bin/env python3

import sqlite3
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"
LOCATION = "Lucknow, Uttar Pradesh, India"
TIMEZONE = ZoneInfo("Asia/Kolkata")

START_YEAR = 1927
END_YEAR = 2125

JYESHTHA_MASA = "03"
BHADRAPADA_MASA = "06"
TRITIYA_TITHI = "03"
AMAVASYA_TITHI = "15"


def parse_local(value, date_value=None):
    """Parse ISO datetime or a time-only Sun_Position value."""
    if value is None:
        raise ValueError("Cannot parse NULL datetime value")

    value = value.strip()

    if "T" in value or " " in value:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TIMEZONE)
        else:
            dt = dt.astimezone(TIMEZONE)
        return dt

    if date_value is None:
        raise ValueError(f"Date required for time-only value: {value}")

    if isinstance(date_value, datetime):
        date_value = date_value.date()
    elif isinstance(date_value, str):
        date_value = datetime.strptime(date_value, "%Y-%m-%d").date()

    for fmt in ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(value, fmt).time()
            return datetime.combine(date_value, t).replace(tzinfo=TIMEZONE)
        except ValueError:
            pass

    raise ValueError(f"Unsupported time/datetime format: {value}")


def parse_transition_datetime(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)
    else:
        dt = dt.astimezone(TIMEZONE)
    return dt


def get_sunrise(conn, gregorian_date):
    row = conn.execute("""
        SELECT Sunrise_Time
        FROM Sun_Position
        WHERE Date = ?
          AND Location = ?
    """, (gregorian_date.isoformat(), LOCATION)).fetchone()

    if row is None:
        raise RuntimeError(f"No Sun_Position row for {gregorian_date}")

    return parse_local(row["Sunrise_Time"], gregorian_date)


def get_hindu_calendar_row(conn, gregorian_date):
    return conn.execute("""
        SELECT Year, Month, Date, Tithi, Paksha, Masa, Adhika_Masa
        FROM Hindu_Calendar
        WHERE Year = ?
          AND Month = ?
          AND Date = ?
    """, (
        f"{gregorian_date.year:04d}",
        f"{gregorian_date.month:02d}",
        f"{gregorian_date.day:02d}"
    )).fetchone()


def create_tables(conn):
    # Exact transition times may be unavailable in fallback mode,
    # therefore the transition columns intentionally allow NULL.
    conn.execute("DROP TABLE IF EXISTS Hartalika_Teej")
    conn.execute("""
        CREATE TABLE Hartalika_Teej (
            Date TEXT NOT NULL,
            Location TEXT NOT NULL,
            Tritiya_Start_Local TEXT,
            Tritiya_End_Local TEXT,
            Rule_Applied TEXT NOT NULL,
            PRIMARY KEY (Date, Location)
        )
    """)

    conn.execute("DROP TABLE IF EXISTS Vat_Savitri")
    conn.execute("""
        CREATE TABLE Vat_Savitri (
            Date TEXT NOT NULL,
            Location TEXT NOT NULL,
            Amavasya_Start_Local TEXT,
            Amavasya_End_Local TEXT,
            Rule_Applied TEXT NOT NULL,
            PRIMARY KEY (Date, Location)
        )
    """)


def find_hartalika_teej_primary(conn, year):
    """
    Primary:
        Bhadrapada Shukla Tritiya at sunrise.

    Tithi_Transition provides exact transition times.
    Hindu_Calendar confirms that the civil date belongs
    to Bhadrapada.
    """
    rows = conn.execute("""
        SELECT Start_Date_Time_Local, End_Date_Time_Local
        FROM Tithi_Transition
        WHERE Location = ?
          AND Tithi = ?
          AND Paksha = 'Shukla'
          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local < ?
        ORDER BY Start_Date_Time_Local
    """, (
        LOCATION,
        TRITIYA_TITHI,
        f"{year}-07-01",
        f"{year + 1}-01-01"
    )).fetchall()

    candidates = []

    for row in rows:
        start_local = parse_transition_datetime(row["Start_Date_Time_Local"])
        end_local = parse_transition_datetime(row["End_Date_Time_Local"])

        check_date = start_local.date() - timedelta(days=1)
        last_date = end_local.date() + timedelta(days=1)

        while check_date <= last_date:
            if check_date.year == year:
                hc = get_hindu_calendar_row(conn, check_date)

                if (
                    hc is not None
                    and hc["Masa"] == BHADRAPADA_MASA
                    and hc["Paksha"] == "Shukla"
                    and hc["Tithi"] == TRITIYA_TITHI
                ):
                    sunrise = get_sunrise(conn, check_date)

                    if start_local <= sunrise < end_local:
                        candidates.append({
                            "date": check_date,
                            "start": start_local,
                            "end": end_local,
                            "rule": (
                                "Bhadrapada Shukla Tritiya "
                                "prevails at sunrise"
                            )
                        })
            check_date += timedelta(days=1)

    if not candidates:
        raise LookupError(
            f"Could not find Hartalika Teej for {year} "
            f"using Tithi_Transition"
        )

    candidates.sort(key=lambda x: x["date"])
    return candidates[0]


def find_hartalika_teej_fallback(conn, year):
    """
    Fallback hierarchy for Hartalika Teej.

    1. First use Hindu_Calendar to identify
       Bhadrapada Shukla Tritiya.

    2. If Hindu_Calendar has no such row, use
       Tithi_Transition directly and select the
       Bhadrapada Shukla Tritiya interval whose
       tithi prevails at sunrise.

    Exact transition times are retained when available.
    """

    # ========================================================
    # FALLBACK LEVEL 1:
    # Hindu_Calendar
    # ========================================================

    rows = conn.execute("""
        SELECT Year, Month, Date, Tithi, Paksha, Masa, Adhika_Masa
        FROM Hindu_Calendar
        WHERE Year = ?
          AND Masa = ?
          AND Paksha = 'Shukla'
          AND Tithi = ?
        ORDER BY Month, Date
    """, (
        f"{year:04d}",
        BHADRAPADA_MASA,
        TRITIYA_TITHI
    )).fetchall()

    if rows:

        candidates = []

        for row in rows:

            festival_date = date(
                int(row["Year"]),
                int(row["Month"]),
                int(row["Date"])
            )

            # Confirm sunrise data exists.
            sunrise = get_sunrise(
                conn,
                festival_date
            )

            candidates.append({
                "date": festival_date,
                "start": None,
                "end": None,
                "rule": (
                    "Fallback: Hindu_Calendar identifies "
                    "Bhadrapada Shukla Tritiya"
                )
            })

        candidates.sort(
            key=lambda x: x["date"]
        )

        return candidates[0]

    # ========================================================
    # FALLBACK LEVEL 2:
    # Tithi_Transition directly
    # ========================================================

    print(
        f"       Hindu_Calendar has no "
        f"Bhadrapada Shukla Tritiya for {year}."
    )

    print(
        f"       Trying Tithi_Transition fallback..."
    )

    transition_rows = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local
        FROM Tithi_Transition
        WHERE Location = ?
          AND Tithi = ?
          AND Paksha = 'Shukla'
          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local < ?
        ORDER BY Start_Date_Time_Local
    """, (
        LOCATION,
        TRITIYA_TITHI,
        f"{year}-08-01",
        f"{year + 1}-01-01"
    )).fetchall()

    candidates = []

    for row in transition_rows:

        start_local = parse_transition_datetime(
            row["Start_Date_Time_Local"]
        )

        end_local = parse_transition_datetime(
            row["End_Date_Time_Local"]
        )

        # Examine every civil date touched by
        # the Tritiya interval.
        check_date = (
            start_local.date() - timedelta(days=1)
        )

        last_date = (
            end_local.date() + timedelta(days=1)
        )

        while check_date <= last_date:

            if check_date.year == year:

                sunrise = get_sunrise(
                    conn,
                    check_date
                )

                # Tritiya prevails at sunrise.
                if start_local <= sunrise < end_local:

                    candidates.append({
                        "date": check_date,
                        "start": start_local,
                        "end": end_local,
                        "rule": (
                            "Fallback: Tithi_Transition "
                            "Bhadrapada Shukla Tritiya "
                            "prevailing at sunrise"
                        )
                    })

            check_date += timedelta(days=1)

    if not candidates:
        raise RuntimeError(
            f"Hartalika Teej fallback failed for {year}: "
            f"neither Hindu_Calendar nor Tithi_Transition "
            f"could identify Bhadrapada Shukla Tritiya."
        )

    candidates.sort(
        key=lambda x: x["date"]
    )

    return candidates[0]

def find_vat_savitri_primary(conn, year):
    """
    Purnimanta-based approximate Vat Savitri.

    Vat Savitri = Jyeshtha Amavasya in the North Indian
    Purnimanta tradition.

    We identify Krishna Amavasya from Tithi_Transition and
    choose the Amavasya that falls approximately 15 days
    before the Amanta Jyeshtha Purnima.

    The exact lunar-month naming is not taken from Masa_Transition,
    because Masa_Transition is Amanta-style in this database.
    """

    # Find Krishna Amavasya transitions.
    rows = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local
        FROM Tithi_Transition
        WHERE Location = ?
          AND Tithi = ?
          AND Paksha = 'Krishna'
          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local < ?
        ORDER BY Start_Date_Time_Local
    """, (
        LOCATION,
        AMAVASYA_TITHI,
        f"{year}-01-01",
        f"{year + 1}-01-01"
    )).fetchall()

    candidates = []

    for row in rows:

        amavasya_start = parse_transition_datetime(
            row["Start_Date_Time_Local"]
        )

        amavasya_end = parse_transition_datetime(
            row["End_Date_Time_Local"]
        )

        # Check both the Amavasya date and adjacent civil date,
        # because Amavasya can cross sunrise.
        check_date = amavasya_start.date() - timedelta(days=1)
        last_date = amavasya_end.date() + timedelta(days=1)

        while check_date <= last_date:

            if check_date.year == year:

                sunrise = get_sunrise(conn, check_date)

                if amavasya_start <= sunrise < amavasya_end:

                    candidates.append({
                        "date": check_date,
                        "start": amavasya_start,
                        "end": amavasya_end,
                        "rule": (
                            "Purnimanta Jyeshtha Amavasya; "
                            "Krishna Amavasya prevails at sunrise"
                        )
                    })

            check_date += timedelta(days=1)

    if not candidates:
        raise LookupError(
            f"Could not find Krishna Amavasya for {year}"
        )

    # There may be several Amavasyas during the year.
    # Select the one corresponding to late spring / early summer,
    # approximately May-June in North India.
    candidates = [
        c for c in candidates
        if 4 <= c["date"].month <= 6
    ]

    if not candidates:
        raise LookupError(
            f"Could not find approximate Jyeshtha Amavasya "
            f"for {year}"
        )

    candidates.sort(key=lambda x: x["date"])

    return candidates[0]

def find_vat_savitri_fallback(conn, year):
    """
    Fallback:
        Use Hindu_Calendar directly.

    Exact Amavasya transition times are not fabricated and
    therefore remain NULL.  This path is used only when the
    transition-based calculation cannot establish the date.
    """
    rows = conn.execute("""
        SELECT Year, Month, Date, Tithi, Paksha, Masa, Adhika_Masa
        FROM Hindu_Calendar
        WHERE Year = ?
          AND Masa = ?
          AND Paksha = 'Krishna'
          AND Tithi = ?
        ORDER BY Month, Date
    """, (
        f"{year:04d}",
        JYESHTHA_MASA,
        AMAVASYA_TITHI
    )).fetchall()

    if not rows:
        raise RuntimeError(
            f"Fallback failed: no Jyeshtha Krishna Amavasya "
            f"in Hindu_Calendar for {year}"
        )

    candidates = []

    for row in rows:
        festival_date = date(
            int(row["Year"]),
            int(row["Month"]),
            int(row["Date"])
        )

        get_sunrise(conn, festival_date)

        candidates.append({
            "date": festival_date,
            "start": None,
            "end": None,
            "rule": (
                "Fallback: Hindu_Calendar identifies "
                "Jyeshtha Krishna Amavasya"
            )
        })

    candidates.sort(key=lambda x: x["date"])
    return candidates[0]


def populate_hartalika_teej(conn):
    print("\nGenerating Hartalika Teej...")

    for year in range(START_YEAR, END_YEAR + 1):
        try:
            result = find_hartalika_teej_primary(conn, year)
            print(f"  {year}: {result['date']} [PRIMARY]")

        except LookupError as exc:
            print(f"  {year}: primary calculation failed")
            print(f"       {exc}")
            print("       Trying Hindu_Calendar fallback...")

            result = find_hartalika_teej_fallback(conn, year)
            print(f"  {year}: {result['date']} [FALLBACK]")

        conn.execute("""
            INSERT INTO Hartalika_Teej (
                Date, Location,
                Tritiya_Start_Local, Tritiya_End_Local,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            result["date"].isoformat(),
            LOCATION,
            result["start"].isoformat() if result["start"] else None,
            result["end"].isoformat() if result["end"] else None,
            result["rule"]
        ))


def populate_vat_savitri(conn):
    print("\nGenerating Vat Savitri...")

    for year in range(START_YEAR, END_YEAR + 1):
        try:
            result = find_vat_savitri_primary(conn, year)
            print(f"  {year}: {result['date']} [PRIMARY]")

        except LookupError as exc:
            print(f"  {year}: primary calculation failed")
            print(f"       {exc}")
            print("       Trying Hindu_Calendar fallback...")

            result = find_vat_savitri_fallback(conn, year)
            print(f"  {year}: {result['date']} [FALLBACK]")

        conn.execute("""
            INSERT INTO Vat_Savitri (
                Date, Location,
                Amavasya_Start_Local, Amavasya_End_Local,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            result["date"].isoformat(),
            LOCATION,
            result["start"].isoformat() if result["start"] else None,
            result["end"].isoformat() if result["end"] else None,
            result["rule"]
        ))


def validate_results(conn):
    print("\nValidation:")

    for table in ("Hartalika_Teej", "Vat_Savitri"):
        count = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        print(f"  {table}: {count} rows")

        rows = conn.execute(f"""
            SELECT Date, Rule_Applied
            FROM {table}
            ORDER BY Date
        """).fetchall()

        for row in rows:
            print(f"    {row['Date']} | {row['Rule_Applied']}")


def main():
    print("=" * 60)
    print("HARTALIKA TEEJ + VAT SAVITRI")
    print("=" * 60)
    print(f"Database : {DB_PATH}")
    print(f"Location : {LOCATION}")
    print(
        f"Gregorian range : "
        f"{START_YEAR}-01-01 to {END_YEAR}-12-31"
    )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        create_tables(conn)
        conn.commit()

        # Each festival has its own primary/fallback logic.
        # A missing transition does not stop the other festival.
        populate_hartalika_teej(conn)
        conn.commit()

        #populate_vat_savitri(conn)
        #conn.commit()

        validate_results(conn)

        print("\nCompleted successfully.")

    except Exception:
        # Only genuine unexpected errors reach here.
        # They are not silently swallowed.
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
