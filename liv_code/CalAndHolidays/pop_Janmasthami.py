
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
        CREATE TABLE IF NOT EXISTS Janmashtami (
            Date TEXT NOT NULL,
            Location TEXT NOT NULL,
            Ashtami_Start_Local TEXT NOT NULL,
            Ashtami_End_Local TEXT NOT NULL,
            Nishita_Start_Local TEXT NOT NULL,
            Nishita_End_Local TEXT NOT NULL,
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
    Parse datetime values stored by the astronomical scripts.

    Examples supported:

        2024-09-03T07:25:38.090470+05:30
        2024-09-03 07:25:38
        2024-09-03 07:25:38.123456

    If no timezone is present, Asia/Kolkata is assumed.
    """

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)

    return dt


# ============================================================
# FORMAT DATETIME
# ============================================================

def format_local_datetime(dt):

    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# FIND BHADRAPADA MASA TRANSITION
# ============================================================

def get_bhadrapada_transition(conn, year):

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
          AND Masa_Number = '06'
          AND Start_Date_Time_Local LIKE ?
        ORDER BY Start_Date_Time_Local
        LIMIT 1
    """, (
        LOCATION,
        f"{year}-%"
    )).fetchone()

    return row


# ============================================================
# FIND RELEVANT KRISHNA ASHTAMI
# ============================================================

def find_krishna_ashtami(conn, masa_start_local):

    masa_start = parse_local_datetime(
        masa_start_local
    )

    # The relevant Krishna Ashtami occurs before
    # the beginning of Masa 06 in this calendar system.
    #
    # Search a generous window.
    search_start = masa_start - timedelta(days=20)
    search_end = masa_start + timedelta(days=1)

    rows = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Tithi,
            Paksha
        FROM Tithi_Transition
        WHERE Location = ?
          AND Paksha = 'Krishna'
          AND Tithi = '08'
          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local <= ?
        ORDER BY Start_Date_Time_Local
    """, (
        LOCATION,
        search_start.isoformat(),
        search_end.isoformat()
    )).fetchall()

    if not rows:

        raise RuntimeError(
            "No Krishna Ashtami transition found near "
            f"Bhadrapada start {masa_start_local}"
        )

    candidates = []

    for row in rows:

        start = parse_local_datetime(
            row["Start_Date_Time_Local"]
        )

        if start < masa_start:

            candidates.append(row)

    if not candidates:

        raise RuntimeError(
            "No Krishna Ashtami found before "
            f"Bhadrapada transition {masa_start_local}"
        )

    # Latest Krishna Ashtami before Masa 06.
    return candidates[-1]


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
# CONVERT SUNSET / SUNRISE TO DATETIME
# ============================================================

def combine_date_time(date_string, time_string):

    return datetime.fromisoformat(
        f"{date_string}T{time_string}"
    ).replace(
        tzinfo=TIMEZONE
    )


# ============================================================
# NISHITA KAAL
# ============================================================

def calculate_nishita(conn, festival_date):

    """
    Night is:

        sunset on festival date
              ->
        sunrise on following date

    Nishita is the central quarter of that night.

    Therefore:

        midpoint = sunset + night / 2

        Nishita start = midpoint - night / 8
        Nishita end   = midpoint + night / 8
    """

    current_date_string = festival_date.strftime(
        "%Y-%m-%d"
    )

    next_date = festival_date + timedelta(days=1)

    next_date_string = next_date.strftime(
        "%Y-%m-%d"
    )

    current_sun = get_sun_position(
        conn,
        current_date_string
    )

    next_sun = get_sun_position(
        conn,
        next_date_string
    )

    sunset = combine_date_time(
        current_sun["Date"],
        current_sun["Sunset_Time"]
    )

    sunrise_next = combine_date_time(
        next_sun["Date"],
        next_sun["Sunrise_Time"]
    )

    night_duration = sunrise_next - sunset

    midpoint = sunset + night_duration / 2

    nishita_half_width = night_duration / 8

    nishita_start = midpoint - nishita_half_width

    nishita_end = midpoint + nishita_half_width

    return nishita_start, nishita_end


# ============================================================
# CHECK WHETHER ASHTAMI PREVAILS AT SUNRISE
# ============================================================

def ashtami_at_sunrise(conn, festival_date,
                       ashtami_start, ashtami_end):

    """
    Krishna Ashtami prevails at sunrise when:

        Ashtami_Start <= Sunrise < Ashtami_End
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
        ashtami_start <= sunrise
        and
        sunrise < ashtami_end
    )


# ============================================================
# CHECK NISHITA OVERLAP
# ============================================================

def ashtami_during_nishita(
    ashtami_start,
    ashtami_end,
    nishita_start,
    nishita_end
):

    """
    True if Krishna Ashtami is prevailing at any instant
    during Nishita Kaal.
    """

    return (
        ashtami_start < nishita_end
        and
        ashtami_end > nishita_start
    )


# ============================================================
# FIND JANMASHTAMI DATE
# ============================================================

def determine_janmashtami_date(
    conn,
    ashtami_start,
    ashtami_end
):

    """
    Primary rule:

        Krishna Ashtami must prevail during Nishita Kaal.

    If both consecutive dates qualify:

        choose the earlier date.

    FALLBACK:

        If neither date has Ashtami during Nishita,
        choose the earlier date on which Krishna Ashtami
        prevails at sunrise.

    This handles cases such as 1963 where Ashtami ended
    shortly before Nishita began.
    """

    first_date = ashtami_start.date()

    last_date = ashtami_end.date()

    # --------------------------------------------------------
    # We examine every civil date touched by the Ashtami
    # interval. Normally this is one or two dates.
    # --------------------------------------------------------

    dates_to_check = []

    current_date = first_date

    while current_date <= last_date:

        dates_to_check.append(current_date)

        current_date += timedelta(days=1)

    # --------------------------------------------------------
    # PRIMARY RULE: Nishita overlap
    # --------------------------------------------------------

    nishita_candidates = []

    print()
    print("PRIMARY RULE: Krishna Ashtami during Nishita")

    for date in dates_to_check:

        nishita_start, nishita_end = calculate_nishita(
            conn,
            date
        )

        qualifies = ashtami_during_nishita(
            ashtami_start,
            ashtami_end,
            nishita_start,
            nishita_end
        )

        print()
        print(
            f"Date checked: {date}"
        )

        print(
            f"  Nishita Kaal: "
            f"{format_local_datetime(nishita_start)}"
            f" -> "
            f"{format_local_datetime(nishita_end)}"
        )

        print(
            f"  Ashtami: "
            f"{format_local_datetime(ashtami_start)}"
            f" -> "
            f"{format_local_datetime(ashtami_end)}"
        )

        print(
            f"  Nishita overlap: "
            f"{'YES' if qualifies else 'NO'}"
        )

        if qualifies:

            nishita_candidates.append(
                (
                    date,
                    nishita_start,
                    nishita_end
                )
            )

    # --------------------------------------------------------
    # If one or more dates qualify, select the earliest.
    # --------------------------------------------------------

    if nishita_candidates:

        nishita_candidates.sort(
            key=lambda item: item[0]
        )

        selected_date, nishita_start, nishita_end = (
            nishita_candidates[0]
        )

        return (
            selected_date,
            nishita_start,
            nishita_end,
            "NISHITA"
        )

    # --------------------------------------------------------
    # FALLBACK RULE
    # --------------------------------------------------------

    print()
    print(
        "PRIMARY RULE FAILED FOR ALL DATES."
    )

    print(
        "Applying fallback: Krishna Ashtami must "
        "prevail at sunrise."
    )

    sunrise_candidates = []

    for date in dates_to_check:

        qualifies = ashtami_at_sunrise(
            conn,
            date,
            ashtami_start,
            ashtami_end
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
            f"  Ashtami at sunrise: "
            f"{'YES' if qualifies else 'NO'}"
        )

        if qualifies:

            sunrise_candidates.append(
                date
            )

    # --------------------------------------------------------
    # Select earliest sunrise-qualified date.
    # --------------------------------------------------------

    if sunrise_candidates:

        selected_date = min(
            sunrise_candidates
        )

        # Even though Nishita did not qualify, store the
        # actual Nishita interval for informational purposes.
        nishita_start, nishita_end = calculate_nishita(
            conn,
            selected_date
        )

        return (
            selected_date,
            nishita_start,
            nishita_end,
            "SUNRISE_FALLBACK"
        )

    # --------------------------------------------------------
    # Nothing qualifies.
    # --------------------------------------------------------

    raise RuntimeError(
        "Krishna Ashtami neither prevailed during Nishita "
        "nor at sunrise on any civil date touched by the "
        "Ashtami transition."
    )


# ============================================================
# PROCESS ONE YEAR
# ============================================================

def process_year(conn, year):

    print()
    print("=" * 70)
    print(f"PROCESSING JANMASHTAMI {year}")
    print("=" * 70)

    conn.execute("BEGIN")

    try:

        # ----------------------------------------------------
        # Remove old result for this year.
        # ----------------------------------------------------

        conn.execute("""
            DELETE FROM Janmashtami
            WHERE Location = ?
              AND Date LIKE ?
        """, (
            LOCATION,
            f"{year}-%"
        ))

        # ----------------------------------------------------
        # Find Masa 06 / Bhadrapada.
        # ----------------------------------------------------

        masa_row = get_bhadrapada_transition(
            conn,
            year
        )

        if masa_row is None:

            raise RuntimeError(
                f"No Masa 06 (Bhadrapada) transition "
                f"found for {year}"
            )

        masa_start = masa_row[
            "Start_Date_Time_Local"
        ]

        masa_end = masa_row[
            "End_Date_Time_Local"
        ]

        print()
        print("Bhadrapada Masa transition:")

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
        # Find Krishna Ashtami.
        # ----------------------------------------------------

        ashtami = find_krishna_ashtami(
            conn,
            masa_start
        )

        ashtami_start = parse_local_datetime(
            ashtami["Start_Date_Time_Local"]
        )

        ashtami_end = parse_local_datetime(
            ashtami["End_Date_Time_Local"]
        )

        print()
        print("Relevant Krishna Ashtami:")

        print(
            f"  {ashtami['Start_Date_Time_Local']}"
            f" -> "
            f"{ashtami['End_Date_Time_Local']}"
        )

        print(
            f"  Tithi: "
            f"{ashtami['Paksha']} "
            f"{ashtami['Tithi']}"
        )

        # ----------------------------------------------------
        # Determine festival date.
        # ----------------------------------------------------

        (
            festival_date,
            nishita_start,
            nishita_end,
            rule_used
        ) = determine_janmashtami_date(
            conn,
            ashtami_start,
            ashtami_end
        )

        # ----------------------------------------------------
        # Rule description.
        # ----------------------------------------------------

        if rule_used == "NISHITA":

            rule_applied = (
                "Krishna Ashtami prevails during Nishita "
                "Kaal; if both consecutive dates qualify, "
                "the earlier date is selected."
            )

        else:

            rule_applied = (
                "Primary Nishita rule did not qualify; "
                "fallback applied: Krishna Ashtami prevails "
                "at sunrise; if multiple dates qualify, "
                "the earlier date is selected."
            )

        # ----------------------------------------------------
        # Insert result.
        # ----------------------------------------------------

        conn.execute("""
            INSERT INTO Janmashtami (
                Date,
                Location,
                Ashtami_Start_Local,
                Ashtami_End_Local,
                Nishita_Start_Local,
                Nishita_End_Local,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            festival_date.strftime("%Y-%m-%d"),
            LOCATION,
            format_local_datetime(ashtami_start),
            format_local_datetime(ashtami_end),
            format_local_datetime(nishita_start),
            format_local_datetime(nishita_end),
            rule_applied
        ))

        # ----------------------------------------------------
        # Commit this year.
        # ----------------------------------------------------

        conn.commit()

        print()
        print("=" * 70)

        print(
            f"Janmashtami Date: "
            f"{festival_date.strftime('%Y-%m-%d')}"
        )

        print(
            f"Ashtami: "
            f"{format_local_datetime(ashtami_start)}"
            f" -> "
            f"{format_local_datetime(ashtami_end)}"
        )

        print(
            f"Nishita Kaal: "
            f"{format_local_datetime(nishita_start)}"
            f" -> "
            f"{format_local_datetime(nishita_end)}"
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
    print("JANMASHTAMI POPULATION")
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
    print("JANMASHTAMI PROCESSING COMPLETE")
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
