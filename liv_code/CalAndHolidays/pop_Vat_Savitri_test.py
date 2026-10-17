#!/usr/bin/env python3

import sqlite3
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# Configuration
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"
LATITUDE = 26.8467
LONGITUDE = 80.9462
TIMEZONE = ZoneInfo("Asia/Kolkata")

START_YEAR = 2024
END_YEAR = 2027

START_DATE = date(START_YEAR, 1, 1)
END_DATE = date(END_YEAR + 1, 1, 1)


# ============================================================
# Helpers
# ============================================================

def parse_local(value):
    """
    Parse an ISO local datetime stored in the database.
    """
    value = value.strip()

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)
    else:
        dt = dt.astimezone(TIMEZONE)

    return dt


def format_local(dt):
    """
    Store local datetime as ISO-8601 with timezone.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)
    else:
        dt = dt.astimezone(TIMEZONE)

    return dt.isoformat()


def daylight_date_sunrise(conn, target_date):
    """
    Return the sunrise time for a given date.

    This is retained as a helper because Vat Savitri is a
    sunrise-based observance. The present implementation
    selects the civil date from the Purnimanta Amavasya interval.
    """

    row = conn.execute(
        """
        SELECT Sunrise_Time
        FROM Sun_Position
        WHERE Date = ?
          AND Location = ?
        """,
        (target_date.isoformat(), LOCATION)
    ).fetchone()

    if row is None:
        return None

    return parse_time_only(row[0], target_date)


def parse_time_only(value, target_date):
    """
    Convert a time-only database value to timezone-aware datetime.
    """
    value = value.strip()

    for fmt in ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(value, fmt).time()
            return datetime.combine(
                target_date,
                t
            ).replace(tzinfo=TIMEZONE)
        except ValueError:
            pass

    raise ValueError(
        f"Unsupported time format: {value}"
    )


# ============================================================
# Read Purnimanta Amavasya intervals
# ============================================================

def get_jyeshtha_amavasya(conn):
    """
    Get Jyeshtha Krishna Amavasya intervals from the
    already-populated Purnimanta_Tithi_Transition table.
    """

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_UTC,
            End_Date_Time_UTC,
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Masa,
            Masa_Type,
            Tithi,
            Paksha
        FROM Purnimanta_Tithi_Transition
        WHERE Location = ?
          AND Masa = '03'
          AND Tithi = '15'
          AND Paksha = 'Krishna'
          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local < ?
        ORDER BY Start_Date_Time_Local
        """,
        (
            LOCATION,
            START_DATE.isoformat(),
            END_DATE.isoformat()
        )
    ).fetchall()

    return rows


# ============================================================
# Determine Vat Savitri date
# ============================================================

def find_vat_savitri_dates(conn):
    """
    Determine Vat Savitri dates from Jyeshtha Krishna Amavasya.

    For the North Indian/Purnimanta convention, the observance
    is associated with Jyeshtha Krishna Amavasya.

    We first identify the exact Amavasya interval and then find
    which civil date contains the Amavasya at sunrise.

    If Amavasya is present at sunrise, that date is selected.

    If Amavasya crosses midnight and is not present at sunrise,
    the date on which the Amavasya interval starts is used as
    the fallback.
    """

    amavasya_rows = get_jyeshtha_amavasya(conn)

    results = []

    for row in amavasya_rows:

        (
            start_utc,
            end_utc,
            start_local_text,
            end_local_text,
            masa,
            masa_type,
            tithi,
            paksha
        ) = row

        start_local = parse_local(start_local_text)
        end_local = parse_local(end_local_text)

        # ----------------------------------------------------
        # Check each civil date touched by the Amavasya.
        # ----------------------------------------------------

        candidate_date = start_local.date()

        while candidate_date <= end_local.date():

            sunrise = daylight_date_sunrise(
                conn,
                candidate_date
            )

            if sunrise is not None:

                # Amavasya prevails at sunrise.
                if start_local <= sunrise < end_local:

                    results.append({
                        "Date": candidate_date.isoformat(),
                        "Location": LOCATION,
                        "Amavasya_Start_Local": format_local(
                            start_local
                        ),
                        "Amavasya_End_Local": format_local(
                            end_local
                        ),
                        "Rule_Applied":
                            "Purnimanta Jyeshtha Krishna Amavasya "
                            "prevailing at sunrise"
                    })

                    break

            candidate_date += timedelta(days=1)

        else:
            # ------------------------------------------------
            # Fallback:
            # If sunrise data cannot identify the date, use
            # the civil date on which Amavasya begins.
            # ------------------------------------------------

            results.append({
                "Date": start_local.date().isoformat(),
                "Location": LOCATION,
                "Amavasya_Start_Local": format_local(
                    start_local
                ),
                "Amavasya_End_Local": format_local(
                    end_local
                ),
                "Rule_Applied":
                    "Purnimanta Jyeshtha Krishna Amavasya "
                    "fallback to Amavasya start date"
            })

    return results


# ============================================================
# Create table
# ============================================================

def create_table(conn):

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Vat_Savitri (
            Date TEXT NOT NULL,
            Location TEXT NOT NULL,
            Amavasya_Start_Local TEXT,
            Amavasya_End_Local TEXT,
            Rule_Applied TEXT NOT NULL,
            PRIMARY KEY (Date, Location)
        )
        """
    )

    conn.commit()


# ============================================================
# Populate table
# ============================================================

def populate_vat_savitri(conn, results):

    # Remove only the requested location/year range.
    conn.execute(
        """
        DELETE FROM Vat_Savitri
        WHERE Location = ?
          AND Date >= ?
          AND Date < ?
        """,
        (
            LOCATION,
            START_DATE.isoformat(),
            END_DATE.isoformat()
        )
    )

    for result in results:

        conn.execute(
            """
            INSERT INTO Vat_Savitri (
                Date,
                Location,
                Amavasya_Start_Local,
                Amavasya_End_Local,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                result["Date"],
                result["Location"],
                result["Amavasya_Start_Local"],
                result["Amavasya_End_Local"],
                result["Rule_Applied"]
            )
        )

    conn.commit()


# ============================================================
# Display results
# ============================================================

def show_results(conn):

    rows = conn.execute(
        """
        SELECT
            Date,
            Amavasya_Start_Local,
            Amavasya_End_Local,
            Rule_Applied
        FROM Vat_Savitri
        WHERE Location = ?
          AND Date >= ?
          AND Date < ?
        ORDER BY Date
        """,
        (
            LOCATION,
            START_DATE.isoformat(),
            END_DATE.isoformat()
        )
    ).fetchall()

    print()
    print("=" * 100)
    print("Vat Savitri")
    print("=" * 100)

    for row in rows:
        print(
            f"Date                  : {row[0]}"
        )
        print(
            f"Amavasya Start Local  : {row[1]}"
        )
        print(
            f"Amavasya End Local    : {row[2]}"
        )
        print(
            f"Rule Applied           : {row[3]}"
        )
        print("-" * 100)

    print(f"Total rows: {len(rows)}")


# ============================================================
# Main
# ============================================================

def main():

    conn = sqlite3.connect(DB_PATH)

    try:

        create_table(conn)

        results = find_vat_savitri_dates(conn)

        print()
        print(
            f"Found {len(results)} Jyeshtha Krishna Amavasya "
            f"candidate(s) for {START_YEAR}-{END_YEAR}."
        )

        for result in results:
            print(
                result["Date"],
                "|",
                result["Amavasya_Start_Local"],
                "->",
                result["Amavasya_End_Local"]
            )

        populate_vat_savitri(conn, results)

        show_results(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
