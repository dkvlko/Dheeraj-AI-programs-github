#!/usr/bin/env python3

import sqlite3
from datetime import date, datetime, timedelta


# ============================================================
# Configuration
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"

START_YEAR = 1927
END_YEAR = 2125


# ============================================================
# Helpers
# ============================================================

def parse_local_datetime(value):
    """
    Parse a local datetime from any of the forms used by the
    transition tables, for example:

        2024-04-21 06:15:47
        2024-04-21T06:15:47.123456+05:30

    The timezone is removed because all comparisons below are
    between local Lucknow clock times.
    """

    return datetime.fromisoformat(value).replace(tzinfo=None)


def sunrise_datetime(conn, civil_date):
    """
    Return local sunrise datetime for a Gregorian date.
    """

    date_string = civil_date.isoformat()

    row = conn.execute(
        """
        SELECT Sunrise_Time
        FROM Sun_Position
        WHERE Date = ?
          AND Location = ?
        """,
        (date_string, LOCATION)
    ).fetchone()

    if row is None:
        raise RuntimeError(
            f"No Sun_Position found for {date_string}"
        )

    return datetime.strptime(
        f"{date_string} {row['Sunrise_Time']}",
        "%Y-%m-%d %H:%M:%S"
    )


def find_tithi(conn, sunrise):
    """
    Find Tithi and Paksha prevailing at local sunrise.
    """

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Tithi,
            Paksha
        FROM Tithi_Transition
        WHERE Location = ?
        ORDER BY Start_Date_Time_Local
        """,
        (LOCATION,)
    )

    for row in rows:

        start = parse_local_datetime(
            row["Start_Date_Time_Local"]
        )

        end = parse_local_datetime(
            row["End_Date_Time_Local"]
        )

        if start <= sunrise < end:
            return (
                row["Tithi"],
                row["Paksha"]
            )

    raise RuntimeError(
        f"No Tithi transition contains sunrise {sunrise}"
    )


def find_nakshatra(conn, sunrise):
    """
    Find Nakshatra prevailing at local sunrise.
    """

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Nakshatra_Number
        FROM Nakshatra_Transition
        WHERE Location = ?
        ORDER BY Start_Date_Time_Local
        """,
        (LOCATION,)
    )

    for row in rows:

        start = parse_local_datetime(
            row["Start_Date_Time_Local"]
        )

        end = parse_local_datetime(
            row["End_Date_Time_Local"]
        )

        if start <= sunrise < end:
            return row["Nakshatra_Number"]

    raise RuntimeError(
        f"No Nakshatra transition contains sunrise {sunrise}"
    )


def find_yoga(conn, sunrise):
    """
    Find Yoga prevailing at local sunrise.

    This assumes Yoga_Transition contains:
        Yoga_Number

    which is analogous to Nakshatra_Transition.
    """

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Yoga_Number
        FROM Yoga_Transition
        WHERE Location = ?
        ORDER BY Start_Date_Time_Local
        """,
        (LOCATION,)
    )

    for row in rows:

        start = parse_local_datetime(
            row["Start_Date_Time_Local"]
        )

        end = parse_local_datetime(
            row["End_Date_Time_Local"]
        )

        if start <= sunrise < end:
            return row["Yoga_Number"]

    raise RuntimeError(
        f"No Yoga transition contains sunrise {sunrise}"
    )


def find_masa(conn, sunrise):
    """
    Find Masa prevailing at local sunrise.

    Masa_Transition is authoritative for the lunar month.

    Returns:
        Masa_Number
        Adhika_Masa
    """

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Masa_Number,
            Masa_Type
        FROM Masa_Transition
        WHERE Location = ?
        ORDER BY Start_Date_Time_Local
        """,
        (LOCATION,)
    )

    for row in rows:

        start = parse_local_datetime(
            row["Start_Date_Time_Local"]
        )

        end = parse_local_datetime(
            row["End_Date_Time_Local"]
        )

        if start <= sunrise < end:

            adhika_masa = (
                1 if row["Masa_Type"] == "Adhika"
                else 0
            )

            return (
                row["Masa_Number"],
                adhika_masa
            )

    raise RuntimeError(
        f"No Masa transition contains sunrise {sunrise}"
    )


# ============================================================
# Main
# ============================================================
#
# Each Gregorian year is processed as its own SQLite transaction.
#
# The connection is opened for one year, all rows for that year
# are deleted/rebuilt, and COMMIT is performed only after the
# complete year has been calculated successfully.
#
# Therefore:
#   - Each completed year is permanently committed.
#   - If the process dies during a year, that year's transaction
#     is rolled back by SQLite.
#   - Previously committed years remain safely in the database.
#   - The database connection is closed after every year and
#     reopened for the next year.
#
# ============================================================

total_inserted = 0

print()
print("=" * 72)
print(
    f"POPULATING HINDU_CALENDAR "
    f"{START_YEAR}-{END_YEAR}"
)
print("=" * 72)

for process_year in range(START_YEAR, END_YEAR + 1):

    print()
    print("-" * 72)
    print(f"Starting year {process_year}")
    print("-" * 72)

    # --------------------------------------------------------
    # Open a fresh connection for this year.
    # --------------------------------------------------------

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:

        # ----------------------------------------------------
        # Check Yoga_Transition schema.
        # ----------------------------------------------------

        yoga_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(Yoga_Transition)"
            )
        }

        if "Yoga_Number" not in yoga_columns:
            raise RuntimeError(
                "Yoga_Transition does not contain "
                "'Yoga_Number'.\n"
                "Run: .schema Yoga_Transition"
            )

        # ----------------------------------------------------
        # Start this year's transaction.
        #
        # Do NOT commit the DELETE separately.
        #
        # This makes the entire year's rebuild atomic:
        #
        #   success -> DELETE + all INSERTs are committed
        #   failure -> DELETE + INSERTs are rolled back
        #
        # Thus an abrupt termination cannot leave a partially
        # calculated year.
        # ----------------------------------------------------

        conn.execute("BEGIN")

        # ----------------------------------------------------
        # Delete existing rows for THIS YEAR only.
        # ----------------------------------------------------

        conn.execute(
            """
            DELETE FROM Hindu_Calendar
            WHERE Year = ?
            """,
            (f"{process_year:04d}",)
        )

        # ----------------------------------------------------
        # Date range for this year.
        # ----------------------------------------------------

        current_date = date(
            process_year,
            1,
            1
        )

        final_date = date(
            process_year + 1,
            1,
            1
        )

        year_inserted = 0

        # ----------------------------------------------------
        # Process every Gregorian date in this year.
        # ----------------------------------------------------

        while current_date < final_date:

            date_string = current_date.isoformat()

            # ------------------------------------------------
            # Sunrise is the reference instant for the daily
            # Panchanga values.
            # ------------------------------------------------

            sunrise = sunrise_datetime(
                conn,
                current_date
            )

            # ------------------------------------------------
            # Tithi
            # ------------------------------------------------

            tithi, paksha = find_tithi(
                conn,
                sunrise
            )

            # ------------------------------------------------
            # Nakshatra
            # ------------------------------------------------

            nakshatra = find_nakshatra(
                conn,
                sunrise
            )

            # ------------------------------------------------
            # Yoga
            # ------------------------------------------------

            yoga = find_yoga(
                conn,
                sunrise
            )

            # ------------------------------------------------
            # Masa
            # ------------------------------------------------

            masa, adhika_masa = find_masa(
                conn,
                sunrise
            )

            # ------------------------------------------------
            # Split Gregorian date into Year / Month / Date.
            # ------------------------------------------------

            year = f"{current_date.year:04d}"
            month = f"{current_date.month:02d}"
            day = f"{current_date.day:02d}"

            # ------------------------------------------------
            # Insert
            # ------------------------------------------------

            conn.execute(
                """
                INSERT INTO Hindu_Calendar (
                    Year,
                    Month,
                    Date,
                    Tithi,
                    Paksha,
                    Nakshatra,
                    Yoga,
                    Masa,
                    Adhika_Masa
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    year,
                    month,
                    day,
                    tithi,
                    paksha,
                    nakshatra,
                    yoga,
                    masa,
                    adhika_masa
                )
            )

            year_inserted += 1
            total_inserted += 1

            # ------------------------------------------------
            # Progress within the current year.
            # ------------------------------------------------

            if year_inserted % 100 == 0:
                print(
                    f"{process_year}: processed "
                    f"{year_inserted} dates; "
                    f"current = {date_string}"
                )

            current_date += timedelta(days=1)

        # ----------------------------------------------------
        # Commit ONLY after the complete year succeeds.
        # ----------------------------------------------------

        conn.commit()

        print(
            f"COMMITTED {process_year}: "
            f"{year_inserted} rows"
        )

    except Exception:
        # ----------------------------------------------------
        # Roll back the current year's transaction.
        # Previously committed years are unaffected.
        # ----------------------------------------------------

        conn.rollback()

        print()
        print(
            f"ERROR while processing {process_year}. "
            f"Rolled back this year's transaction."
        )
        raise

    finally:
        # ----------------------------------------------------
        # Close the connection before moving to the next year.
        # ----------------------------------------------------

        conn.close()

print()
print("=" * 72)
print(
    f"Completed successfully. "
    f"Inserted {total_inserted} Hindu_Calendar rows."
)
print("=" * 72)
