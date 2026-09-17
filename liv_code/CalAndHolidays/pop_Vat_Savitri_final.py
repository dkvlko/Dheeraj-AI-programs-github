#!/usr/bin/env python3

import sqlite3
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import swisseph as swe


# ============================================================
# Configuration
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"
LATITUDE = 26.8467
LONGITUDE = 80.9462

TIMEZONE = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

START_YEAR = 1927
END_YEAR = 2125


# ============================================================
# Parse local datetime
# ============================================================

def parse_local(value):
    """
    Parse an ISO-8601 datetime from the database.

    Example:
        2024-06-05T19:55:27+05:30
    """

    dt = datetime.fromisoformat(
        value.strip()
    )

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=TIMEZONE
        )
    else:
        dt = dt.astimezone(
            TIMEZONE
        )

    return dt


# ============================================================
# Julian Day
# ============================================================

def datetime_to_jd_ut(dt):
    """
    Convert timezone-aware datetime to Julian Day UT.
    """

    dt_utc = dt.astimezone(UTC)

    hour = (
        dt_utc.hour
        + dt_utc.minute / 60.0
        + dt_utc.second / 3600.0
        + dt_utc.microsecond / 3600000000.0
    )

    return swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        hour
    )


# ============================================================
# Sunrise
# ============================================================

def get_sunrise(target_date):
    """
    Calculate sunrise at Lucknow for target_date
    using Swiss Ephemeris.
    """

    # --------------------------------------------------------
    # Use approximately noon UTC on the requested date.
    # This gives Swiss Ephemeris a point safely before the
    # sunrise we want to find.
    # --------------------------------------------------------

    noon_local = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        12,
        0,
        0,
        tzinfo=TIMEZONE
    )

    jd_ut = datetime_to_jd_ut(
        noon_local
    )

    geopos = (
        LONGITUDE,
        LATITUDE,
        0.0
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # pyswisseph argument order is:
    #
    # rise_trans(
    #     tjdut,
    #     body,
    #     rsmi,
    #     geopos
    # )
    #
    # rsmi MUST come before geopos.
    # --------------------------------------------------------

    result = swe.rise_trans(
        jd_ut,
        swe.SUN,
        swe.CALC_RISE,
        geopos
    )

    sunrise_jd_ut = result[1][0]

    year, month, day, hour = swe.revjul(
        sunrise_jd_ut,
        swe.GREG_CAL
    )

    # --------------------------------------------------------
    # Convert fractional hour into H:M:S.
    # --------------------------------------------------------

    hour_int = int(hour)

    minute_float = (
        hour - hour_int
    ) * 60.0

    minute_int = int(minute_float)

    second_float = (
        minute_float - minute_int
    ) * 60.0

    second_int = int(
        round(second_float)
    )

    # Handle rounding.
    if second_int >= 60:
        second_int = 0
        minute_int += 1

    if minute_int >= 60:
        minute_int = 0
        hour_int += 1

    sunrise_utc = datetime(
        year,
        month,
        day,
        hour_int,
        minute_int,
        second_int,
        tzinfo=UTC
    )

    return sunrise_utc.astimezone(
        TIMEZONE
    )


# ============================================================
# Get Jyeshtha Krishna Amavasya for one year
# ============================================================

def get_amavasya_for_year(conn, year):
    """
    Read Jyeshtha Krishna Amavasya from
    Purnimanta_Tithi_Transition.

    Masa:
        03 = Jyeshtha

    Paksha:
        Krishna

    Tithi:
        15 = Amavasya
    """

    year_start = (
        f"{year:04d}-01-01"
    )

    year_end = (
        f"{year + 1:04d}-01-01"
    )

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Masa,
            Masa_Type,
            Tithi,
            Paksha
        FROM Purnimanta_Tithi_Transition
        WHERE Location = ?
          AND Masa = '03'
          AND Paksha = 'Krishna'
          AND Tithi = '15'
          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local < ?
        ORDER BY Start_Date_Time_Local
        """,
        (
            LOCATION,
            year_start,
            year_end
        )
    ).fetchall()

    return rows


# ============================================================
# Calculate Vat Savitri for one year
# ============================================================

def calculate_vat_savitri_for_year(
    conn,
    year
):
    """
    Determine Vat Savitri using:

        Purnimanta Jyeshtha
        Krishna Paksha
        Amavasya
        Amavasya prevailing at sunrise
    """

    rows = get_amavasya_for_year(
        conn,
        year
    )

    if not rows:
        raise RuntimeError(
            f"No Jyeshtha Krishna Amavasya "
            f"found in Purnimanta_Tithi_Transition "
            f"for {year}."
        )

    if len(rows) > 1:
        print(
            f"WARNING: Found {len(rows)} Jyeshtha Krishna "
            f"Amavasya intervals for {year}. "
            f"Selecting the interval nearest to sunrise."
        )

        best_row = None
        best_distance = None

        for row in rows:

            start_local = parse_local(row[0])
            end_local = parse_local(row[1])

            candidate_date = start_local.date()

            while candidate_date <= end_local.date():

                sunrise = get_sunrise(candidate_date)

                # Distance from sunrise to the Amavasya interval.
                #
                # 0 seconds means Amavasya prevails exactly at
                # sunrise, which is the preferred situation.
                if start_local <= sunrise < end_local:

                    distance = 0.0

                elif sunrise < start_local:

                    distance = (
                        start_local - sunrise
                    ).total_seconds()

                else:

                    distance = (
                        sunrise - end_local
                    ).total_seconds()

                if (
                    best_distance is None
                    or distance < best_distance
                ):
                    best_distance = distance
                    best_row = row

                candidate_date += timedelta(days=1)

        rows = [best_row]

        print(
            f"Selected Amavasya interval nearest to sunrise:"
        )
        print(
            f"    Start: {best_row[0]}"
        )
        print(
            f"    End  : {best_row[1]}"
        )
        print(
            f"    Distance from nearest sunrise: "
            f"{best_distance / 3600:.2f} hours"
        )

    (
        start_local_text,
        end_local_text,
        masa,
        masa_type,
        tithi,
        paksha
    ) = rows[0]

    amavasya_start = parse_local(
        start_local_text
    )

    amavasya_end = parse_local(
        end_local_text
    )

    # --------------------------------------------------------
    # Amavasya may cross midnight.
    #
    # Check every civil date touched by the interval.
    # --------------------------------------------------------

    candidate_date = (
        amavasya_start.date()
    )

    while candidate_date <= amavasya_end.date():

        sunrise = get_sunrise(
            candidate_date
        )

        print(
            f"    Checking sunrise "
            f"{candidate_date}: "
            f"{sunrise.isoformat()}"
        )

        # ----------------------------------------------------
        # Amavasya must prevail at sunrise.
        # ----------------------------------------------------

        if (
            amavasya_start
            <= sunrise
            < amavasya_end
        ):

            return {
                "Date":
                    candidate_date.isoformat(),

                "Location":
                    LOCATION,

                "Amavasya_Start_Local":
                    amavasya_start.isoformat(),

                "Amavasya_End_Local":
                    amavasya_end.isoformat(),

                "Rule_Applied":
                    "Purnimanta Jyeshtha Krishna "
                    "Amavasya prevailing at sunrise"
            }

        candidate_date += timedelta(
            days=1
        )

    # --------------------------------------------------------
    # Fallback:
    #
    # If Amavasya does not prevail at sunrise on any date
    # touched by the interval, use the local civil date on
    # which Amavasya begins.
    #
    # This handles cases where Amavasya starts after sunrise
    # on one day and ends before the following sunrise.
    # --------------------------------------------------------

    selected_date = amavasya_start.date()

    return {
        "Date":
            selected_date.isoformat(),

        "Location":
            LOCATION,

        "Amavasya_Start_Local":
            amavasya_start.isoformat(),

        "Amavasya_End_Local":
            amavasya_end.isoformat(),

        "Rule_Applied":
            "Purnimanta Jyeshtha Krishna Amavasya "
            "fallback to Amavasya start date "
            "(no sunrise within Amavasya interval)"
    }

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
# Process and COMMIT one year
# ============================================================

def populate_year(
    conn,
    year
):
    """
    Process exactly one year and commit it before
    the caller moves to the next year.
    """

    print()
    print("=" * 100)
    print(
        f"PROCESSING VAT SAVITRI - {year}"
    )
    print("=" * 100)

    # --------------------------------------------------------
    # Calculate before opening the write transaction.
    # --------------------------------------------------------

    result = calculate_vat_savitri_for_year(
        conn,
        year
    )

    print()
    print(
        f"Vat Savitri Date      : "
        f"{result['Date']}"
    )

    print(
        f"Amavasya Start Local  : "
        f"{result['Amavasya_Start_Local']}"
    )

    print(
        f"Amavasya End Local    : "
        f"{result['Amavasya_End_Local']}"
    )

    print(
        f"Rule Applied          : "
        f"{result['Rule_Applied']}"
    )

    try:

        # ----------------------------------------------------
        # BEGIN TRANSACTION FOR THIS YEAR.
        # ----------------------------------------------------

        conn.execute(
            "BEGIN"
        )

        # ----------------------------------------------------
        # Remove an existing row for this year/location.
        # ----------------------------------------------------

        conn.execute(
            """
            DELETE FROM Vat_Savitri
            WHERE Location = ?
              AND Date >= ?
              AND Date < ?
            """,
            (
                LOCATION,
                f"{year:04d}-01-01",
                f"{year + 1:04d}-01-01"
            )
        )

        # ----------------------------------------------------
        # Insert this year's record.
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # COMMIT IMMEDIATELY.
        #
        # The next year is NOT processed until this finishes.
        # ----------------------------------------------------

        conn.commit()

        print()
        print(
            f"*** YEAR {year} COMMITTED SUCCESSFULLY ***"
        )

    except Exception as e:

        conn.rollback()

        print()
        print(
            f"*** YEAR {year} ROLLED BACK ***"
        )

        raise


# ============================================================
# Display final results
# ============================================================

def display_results(conn):

    rows = conn.execute(
        """
        SELECT
            Date,
            Location,
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
            f"{START_YEAR:04d}-01-01",
            f"{END_YEAR + 1:04d}-01-01"
        )
    ).fetchall()

    print()
    print("=" * 110)
    print("FINAL VAT SAVITRI DATA")
    print("=" * 110)

    for row in rows:

        print(
            f"Date                  : {row[0]}"
        )

        print(
            f"Location              : {row[1]}"
        )

        print(
            f"Amavasya Start Local  : {row[2]}"
        )

        print(
            f"Amavasya End Local    : {row[3]}"
        )

        print(
            f"Rule Applied           : {row[4]}"
        )

        print("-" * 110)

    print(
        f"Total rows: {len(rows)}"
    )

    print("=" * 110)


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("=" * 100)
    print(
        f"VAT SAVITRI POPULATION "
        f"{START_YEAR}-{END_YEAR}"
    )
    print("=" * 100)

    print(
        f"Database : {DB_PATH}"
    )

    print(
        f"Location : {LOCATION}"
    )

    print(
        f"Latitude : {LATITUDE}"
    )

    print(
        f"Longitude: {LONGITUDE}"
    )

    conn = sqlite3.connect(
        DB_PATH
    )

    try:

        # ----------------------------------------------------
        # Create table.
        # ----------------------------------------------------

        create_table(conn)

        # ----------------------------------------------------
        # Process each year independently.
        #
        # populate_year() MUST return only after commit().
        # ----------------------------------------------------

        for year in range(
            START_YEAR,
            END_YEAR + 1
        ):

            populate_year(
                conn,
                year
            )

        # ----------------------------------------------------
        # Display final data.
        # ----------------------------------------------------

        display_results(
            conn
        )

    finally:

        conn.close()


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()
