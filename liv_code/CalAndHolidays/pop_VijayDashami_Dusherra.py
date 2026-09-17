
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

START_YEAR = 1927
END_YEAR = 2125


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# CREATE TABLE
# ============================================================

def create_table(conn):

    conn.execute("""
        CREATE TABLE IF NOT EXISTS Dussehra (
            Date TEXT NOT NULL,
            Location TEXT NOT NULL,
            Dashami_Start_Local TEXT NOT NULL,
            Dashami_End_Local TEXT NOT NULL,
            Aparahna_Start_Local TEXT NOT NULL,
            Aparahna_End_Local TEXT NOT NULL,
            Rule_Applied TEXT NOT NULL,
            PRIMARY KEY (Date, Location)
        )
    """)

    conn.commit()


# ============================================================
# DATETIME PARSER
# ============================================================

def parse_local_datetime(value):

    """
    Parse ISO-8601 datetime values stored in the database.

    Examples:

        2024-10-03T12:34:56.123456+05:30
        2024-10-03 12:34:56

    If no timezone is present, Asia/Kolkata is assumed.
    """

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:

        dt = dt.replace(
            tzinfo=TIMEZONE
        )

    return dt


# ============================================================
# FORMAT DATETIME
# ============================================================

def format_local_datetime(dt):

    return dt.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ============================================================
# FIND ASHVINA MASA
# ============================================================

def get_ashvina_transition(conn, year):

    """
    Masa 07 = Ashvina in the user's Masa table.

    Vijayadashami occurs in the Shukla Paksha of Ashvina.
    """

    row = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Masa_Number,
            Masa_English,
            Masa_Hindi,
            Masa_Type
        FROM Masa_Transition
        WHERE Location = ?
          AND Masa_Number = '07'
          AND Start_Date_Time_Local LIKE ?
        ORDER BY Start_Date_Time_Local
        LIMIT 1
    """, (
        LOCATION,
        f"{year}-%"
    )).fetchone()

    return row


# ============================================================
# FIND SHUKLA DASHAMI
# ============================================================

def find_shukla_dashami(
    conn,
    masa_start_local,
    masa_end_local
):

    """
    Find Shukla Dashami within the Ashvina lunar month.

    Search using the exact Masa_Transition interval.
    """

    rows = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Tithi,
            Paksha
        FROM Tithi_Transition
        WHERE Location = ?
          AND Paksha = 'Shukla'
          AND Tithi = '10'
          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local < ?
        ORDER BY Start_Date_Time_Local
    """, (
        LOCATION,
        masa_start_local,
        masa_end_local
    )).fetchall()

    if not rows:

        raise RuntimeError(
            "No Shukla Dashami transition found inside "
            f"Ashvina Masa: {masa_start_local} -> {masa_end_local}"
        )

    # Normally exactly one Dashami will occur.
    # If more than one somehow exists because of unusual
    # calendar conditions, use the first transition.
    return rows[0]


# ============================================================
# SUN POSITION
# ============================================================

def get_sun_position(conn, date_string):

    row = conn.execute("""
        SELECT
            Date,
            Sunrise_Time,
            Sunset_Time
        FROM Sun_Position
        WHERE Date = ?
          AND Location = ?
    """, (
        date_string,
        LOCATION
    )).fetchone()

    if row is None:

        raise RuntimeError(
            f"No Sun_Position row found for {date_string}"
        )

    return row


# ============================================================
# COMBINE DATE + TIME
# ============================================================

def combine_date_time(
    date_string,
    time_string
):

    return datetime.fromisoformat(
        f"{date_string}T{time_string}"
    ).replace(
        tzinfo=TIMEZONE
    )


# ============================================================
# CALCULATE APARAHNA KAAL
# ============================================================

def calculate_aparahna(
    conn,
    festival_date
):

    """
    Aparahna is the third fifth of the daylight period.

    Daylight:

        Sunrise ---------------- Sunset
             |    |    |    |    |
             1    2    3    4    5

    Aparahna:

                       |---------|
                       3rd fifth

    Therefore:

        Aparahna Start = Sunrise + 2/5 daylight
        Aparahna End   = Sunrise + 3/5 daylight
    """

    date_string = festival_date.strftime(
        "%Y-%m-%d"
    )

    sun = get_sun_position(
        conn,
        date_string
    )

    sunrise = combine_date_time(
        sun["Date"],
        sun["Sunrise_Time"]
    )

    sunset = combine_date_time(
        sun["Date"],
        sun["Sunset_Time"]
    )

    daylight = sunset - sunrise

    aparahna_start = (
        sunrise + daylight * 2 / 5
    )

    aparahna_end = (
        sunrise + daylight * 3 / 5
    )

    return (
        aparahna_start,
        aparahna_end
    )


# ============================================================
# CHECK DASHAMI DURING APARAHNA
# ============================================================

def dashami_during_aparahna(
    dashami_start,
    dashami_end,
    aparahna_start,
    aparahna_end
):

    """
    True when Shukla Dashami is prevailing at some point
    during Aparahna.
    """

    return (
        dashami_start < aparahna_end
        and
        dashami_end > aparahna_start
    )


# ============================================================
# CHECK DASHAMI AT SUNRISE
# ============================================================

def dashami_at_sunrise(
    conn,
    festival_date,
    dashami_start,
    dashami_end
):

    """
    True when Shukla Dashami prevails at sunrise.
    """

    date_string = festival_date.strftime(
        "%Y-%m-%d"
    )

    sun = get_sun_position(
        conn,
        date_string
    )

    sunrise = combine_date_time(
        sun["Date"],
        sun["Sunrise_Time"]
    )

    return (
        dashami_start <= sunrise
        and
        sunrise < dashami_end
    )


# ============================================================
# DETERMINE DUSSEHRA DATE
# ============================================================

def determine_dussehra_date(
    conn,
    dashami_start,
    dashami_end
):

    """
    PRIMARY RULE

    Vijayadashami / Dussehra is the civil date on which
    Shukla Dashami prevails during Aparahna Kaal.

    If both consecutive dates qualify, select the earlier.

    FALLBACK

    If Dashami does not prevail during Aparahna on either
    date, select the earlier civil date on which Shukla
    Dashami prevails at sunrise.
    """

    first_date = dashami_start.date()

    last_date = dashami_end.date()

    dates_to_check = []

    current_date = first_date

    while current_date <= last_date:

        dates_to_check.append(
            current_date
        )

        current_date += timedelta(
            days=1
        )

    # --------------------------------------------------------
    # PRIMARY RULE
    # --------------------------------------------------------

    aparahna_candidates = []

    print()
    print(
        "PRIMARY RULE: Shukla Dashami during Aparahna"
    )

    for date in dates_to_check:

        aparahna_start, aparahna_end = (
            calculate_aparahna(
                conn,
                date
            )
        )

        qualifies = dashami_during_aparahna(
            dashami_start,
            dashami_end,
            aparahna_start,
            aparahna_end
        )

        print()
        print(
            f"Date checked: {date}"
        )

        print(
            f"  Aparahna: "
            f"{format_local_datetime(aparahna_start)}"
            f" -> "
            f"{format_local_datetime(aparahna_end)}"
        )

        print(
            f"  Dashami: "
            f"{format_local_datetime(dashami_start)}"
            f" -> "
            f"{format_local_datetime(dashami_end)}"
        )

        print(
            f"  Aparahna overlap: "
            f"{'YES' if qualifies else 'NO'}"
        )

        if qualifies:

            aparahna_candidates.append(
                (
                    date,
                    aparahna_start,
                    aparahna_end
                )
            )

    # --------------------------------------------------------
    # PRIMARY RULE SUCCEEDED
    # --------------------------------------------------------

    if aparahna_candidates:

        aparahna_candidates.sort(
            key=lambda item: item[0]
        )

        (
            selected_date,
            aparahna_start,
            aparahna_end
        ) = aparahna_candidates[0]

        return (
            selected_date,
            aparahna_start,
            aparahna_end,
            "APARAHNA"
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    print()
    print(
        "PRIMARY RULE FAILED FOR ALL DATES."
    )

    print(
        "Applying fallback: Shukla Dashami must "
        "prevail at sunrise."
    )

    sunrise_candidates = []

    for date in dates_to_check:

        qualifies = dashami_at_sunrise(
            conn,
            date,
            dashami_start,
            dashami_end
        )

        sun = get_sun_position(
            conn,
            date.strftime("%Y-%m-%d")
        )

        sunrise = combine_date_time(
            sun["Date"],
            sun["Sunrise_Time"]
        )

        print()
        print(
            f"Fallback date checked: {date}"
        )

        print(
            f"  Sunrise: "
            f"{format_local_datetime(sunrise)}"
        )

        print(
            f"  Dashami at sunrise: "
            f"{'YES' if qualifies else 'NO'}"
        )

        if qualifies:

            sunrise_candidates.append(
                date
            )

    # --------------------------------------------------------
    # FALLBACK SUCCEEDED
    # --------------------------------------------------------

    if sunrise_candidates:

        selected_date = min(
            sunrise_candidates
        )

        aparahna_start, aparahna_end = (
            calculate_aparahna(
                conn,
                selected_date
            )
        )

        return (
            selected_date,
            aparahna_start,
            aparahna_end,
            "SUNRISE_FALLBACK"
        )

    # --------------------------------------------------------
    # NOTHING QUALIFIES
    # --------------------------------------------------------

    raise RuntimeError(
        "Shukla Dashami neither prevailed during Aparahna "
        "nor at sunrise on any civil date touched by the "
        "Dashami transition."
    )


# ============================================================
# PROCESS ONE YEAR
# ============================================================

def process_year(
    conn,
    year
):

    print()
    print("=" * 70)
    print(
        f"PROCESSING DUSSEHRA / VIJAYADASHAMI {year}"
    )
    print("=" * 70)

    conn.execute("BEGIN")

    try:

        # ----------------------------------------------------
        # Remove old result for this year.
        # ----------------------------------------------------

        conn.execute("""
            DELETE FROM Dussehra
            WHERE Location = ?
              AND Date LIKE ?
        """, (
            LOCATION,
            f"{year}-%"
        ))

        # ----------------------------------------------------
        # Find Ashvina Masa.
        # ----------------------------------------------------

        masa_row = get_ashvina_transition(
            conn,
            year
        )

        if masa_row is None:

            raise RuntimeError(
                f"No Masa 07 (Ashvina) transition found "
                f"for {year}"
            )

        masa_start = masa_row[
            "Start_Date_Time_Local"
        ]

        masa_end = masa_row[
            "End_Date_Time_Local"
        ]

        print()
        print(
            "Ashvina Masa transition:"
        )

        print(
            f"  {masa_start} -> {masa_end}"
        )

        print(
            f"  Masa: "
            f"{masa_row['Masa_Number']} "
            f"{masa_row['Masa_English']} "
            f"{masa_row['Masa_Type']}"
        )

        # ----------------------------------------------------
        # Find Shukla Dashami.
        # ----------------------------------------------------

        dashami = find_shukla_dashami(
            conn,
            masa_start,
            masa_end
        )

        dashami_start = parse_local_datetime(
            dashami["Start_Date_Time_Local"]
        )

        dashami_end = parse_local_datetime(
            dashami["End_Date_Time_Local"]
        )

        print()
        print(
            "Relevant Shukla Dashami:"
        )

        print(
            f"  {dashami['Start_Date_Time_Local']}"
            f" -> "
            f"{dashami['End_Date_Time_Local']}"
        )

        print(
            f"  Tithi: "
            f"{dashami['Paksha']} "
            f"{dashami['Tithi']}"
        )

        # ----------------------------------------------------
        # Determine Dussehra date.
        # ----------------------------------------------------

        (
            festival_date,
            aparahna_start,
            aparahna_end,
            rule_used
        ) = determine_dussehra_date(
            conn,
            dashami_start,
            dashami_end
        )

        # ----------------------------------------------------
        # Rule description.
        # ----------------------------------------------------

        if rule_used == "APARAHNA":

            rule_applied = (
                "Shukla Dashami prevails during Aparahna "
                "Kaal; if both consecutive dates qualify, "
                "the earlier date is selected."
            )

        else:

            rule_applied = (
                "Primary Aparahna rule did not qualify; "
                "fallback applied: Shukla Dashami prevails "
                "at sunrise; if multiple dates qualify, "
                "the earlier date is selected."
            )

        # ----------------------------------------------------
        # Insert result.
        # ----------------------------------------------------

        conn.execute("""
            INSERT INTO Dussehra (
                Date,
                Location,
                Dashami_Start_Local,
                Dashami_End_Local,
                Aparahna_Start_Local,
                Aparahna_End_Local,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            festival_date.strftime(
                "%Y-%m-%d"
            ),
            LOCATION,
            format_local_datetime(
                dashami_start
            ),
            format_local_datetime(
                dashami_end
            ),
            format_local_datetime(
                aparahna_start
            ),
            format_local_datetime(
                aparahna_end
            ),
            rule_applied
        ))

        # ----------------------------------------------------
        # Commit this year independently.
        # ----------------------------------------------------

        conn.commit()

        print()
        print("=" * 70)

        print(
            "Dussehra / Vijayadashami Date: "
            f"{festival_date.strftime('%Y-%m-%d')}"
        )

        print(
            f"Dashami: "
            f"{format_local_datetime(dashami_start)}"
            f" -> "
            f"{format_local_datetime(dashami_end)}"
        )

        print(
            f"Aparahna: "
            f"{format_local_datetime(aparahna_start)}"
            f" -> "
            f"{format_local_datetime(aparahna_end)}"
        )

        print(
            f"Rule Used: {rule_used}"
        )

        print("=" * 70)

        print(
            f"COMMITTED {year}"
        )

    except Exception as exc:

        conn.rollback()

        print()
        print(
            f"ERROR processing {year}: {exc}"
        )

        print(
            f"ROLLED BACK {year}"
        )

        raise


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "DUSSEHRA / VIJAYADASHAMI POPULATION"
    )
    print("=" * 70)

    print(
        f"Database : {DB_PATH}"
    )

    print(
        f"Location : {LOCATION}"
    )

    print(
        f"Years    : {START_YEAR} - {END_YEAR}"
    )

    conn = get_connection()

    try:

        create_table(conn)

        for year in range(
            START_YEAR,
            END_YEAR + 1
        ):

            process_year(
                conn,
                year
            )

    finally:

        conn.close()

    print()
    print("=" * 70)
    print(
        "DUSSEHRA / VIJAYADASHAMI PROCESSING COMPLETE"
    )
    print("=" * 70)


if __name__ == "__main__":

    main()
