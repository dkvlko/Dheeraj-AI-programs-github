
from datetime import datetime, timedelta, timezone
import sqlite3


# ============================================================
# Configuration
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"
LATITUDE = 26.8467
LONGITUDE = 80.9462

START_YEAR = 1927
END_YEAR = 2123


# ============================================================
# Database
# ============================================================

def get_connection():
    return sqlite3.connect(DB_PATH)


# ============================================================
# Datetime utilities
# ============================================================

def parse_dt(value):
    """
    Convert ISO datetime string to timezone-aware datetime.
    """
    return datetime.fromisoformat(value)


def to_utc_string(dt):
    """
    Convert timezone-aware datetime to UTC ISO string.
    """
    return dt.astimezone(timezone.utc).isoformat()


def to_local_string(dt):
    """
    Return local ISO datetime string.
    """
    return dt.isoformat()


# ============================================================
# Interval utilities
# ============================================================

def get_intersection(start1, end1, start2, end2):
    """
    Return intersection of two half-open intervals:

        [start1, end1)
        [start2, end2)

    Returns:
        (start, end)

    or None if there is no overlap.
    """

    start = max(start1, start2)
    end = min(end1, end2)

    if start < end:
        return start, end

    return None


def intervals_overlap(start1, end1, start2, end2):
    """
    Return True when two half-open intervals overlap.
    """
    return start1 < end2 and end1 > start2


# ============================================================
# Sun times
# ============================================================

def get_sun_times(conn, date_string):
    """
    Sun_Position stores Sunrise_Time and Sunset_Time as
    time-only strings, e.g. 06:18:02 and 18:13:38.
    """

    row = conn.execute(
        """
        SELECT Sunrise_Time, Sunset_Time
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
            f"No Sun_Position row found for {date_string}"
        )

    sunrise_string, sunset_string = row

    sunrise = datetime.fromisoformat(
        f"{date_string}T{sunrise_string}+05:30"
    )

    sunset = datetime.fromisoformat(
        f"{date_string}T{sunset_string}+05:30"
    )

    return sunrise, sunset


# ============================================================
# Hindu midnight
# ============================================================

def get_hindu_midnight(conn, date_string):
    """
    Hindu midnight is the midpoint between:

        today's sunset
        next day's sunrise
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
# Find regular Phalguna Purnima
# ============================================================

def get_phalguna_purnima(conn, year):
    """
    Find regular Phalguna Purnima.

    Rules:

        Masa = 12
        Adhika_Masa = 0

    The Purnima interval is taken from:

        Amavasya_Purnima_Transition

    The Hindu_Calendar row corresponding to the Purnima
    START date is used only to identify the Masa.
    """

    row = conn.execute(
        """
        SELECT
            p.Start_Date_Time_Local,
            p.End_Date_Time_Local,

            h.Tithi,
            h.Paksha,
            h.Masa,
            h.Adhika_Masa

        FROM Amavasya_Purnima_Transition p

        JOIN Hindu_Calendar h
          ON h.Year  = strftime('%Y', p.Start_Date_Time_Local)
         AND h.Month = strftime('%m', p.Start_Date_Time_Local)
         AND h.Date  = strftime('%d', p.Start_Date_Time_Local)

        WHERE p.Phase = 'Purnima'
          AND h.Masa = '12'
          AND h.Adhika_Masa = 0
          AND h.Year = ?

        ORDER BY p.Start_Date_Time_Local

        LIMIT 1
        """,
        (
            f"{year:04d}",
        ),
    ).fetchone()

    return row


# ============================================================
# Find Pradosh intervals
# ============================================================

def get_pradosh_for_date(conn, date_string):
    """
    Get Pradosh for a particular civil date.
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
            f"No Daily_Time_Periods row found for {date_string}"
        )

    pradosh_start_string, pradosh_end_string = row

    return (
        parse_dt(pradosh_start_string),
        parse_dt(pradosh_end_string),
    )


# ============================================================
# Find Purnima / Pradosh overlap
# ============================================================

def get_phalguna_purnima_pradosh(
    conn,
    year,
):
    """
    Find the regular Phalguna Purnima interval and the
    Pradosh interval which actually overlaps it.

    IMPORTANT:

    We check BOTH:

        1. Purnima start date
        2. Civil date following Purnima start date

    because Purnima can cross a civil-date boundary.

    We do NOT assume that the relevant Pradosh belongs
    to the Purnima start date.
    """

    purnima = get_phalguna_purnima(
        conn,
        year,
    )

    if purnima is None:
        return None

    (
        purnima_start_string,
        purnima_end_string,
        tithi,
        paksha,
        masa_number,
        adhika_masa,
    ) = purnima

    purnima_start = parse_dt(
        purnima_start_string
    )

    purnima_end = parse_dt(
        purnima_end_string
    )

    start_date = purnima_start.date()

    candidate_dates = [
        start_date,
        start_date + timedelta(days=1),
    ]

    for candidate_date in candidate_dates:

        date_string = candidate_date.isoformat()

        pradosh_start, pradosh_end = (
            get_pradosh_for_date(
                conn,
                date_string,
            )
        )

        overlap = get_intersection(
            purnima_start,
            purnima_end,
            pradosh_start,
            pradosh_end,
        )

        if overlap is not None:

            return {
                "purnima_start_string":
                    purnima_start_string,

                "purnima_end_string":
                    purnima_end_string,

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

                "masa_number":
                    masa_number,

                "adhika_masa":
                    adhika_masa,
            }

    return None


# ============================================================
# Find complete Bhadra intervals
# ============================================================

def get_bhadra_overlaps(
    conn,
    candidate_start,
    candidate_end,
):
    """
    Find complete Bhadra intervals overlapping the
    Holika candidate.

    Karana_Transition is authoritative for complete Bhadra.

    Is_Bhadra = 1 identifies Vishti/Bhadra.
    """

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Karana_Number,
            Karana
        FROM Karana_Transition
        WHERE Location = ?
          AND Is_Bhadra = 1
          AND Start_Date_Time_Local < ?
          AND End_Date_Time_Local > ?
        ORDER BY Start_Date_Time_Local
        """,
        (
            LOCATION,
            candidate_end.isoformat(),
            candidate_start.isoformat(),
        ),
    ).fetchall()

    return rows


# ============================================================
# Find Bhadra Puccha
# ============================================================

def get_bhadra_puccha(
    conn,
    start,
    end,
):
    """
    Find Bhadra Puccha intervals overlapping [start, end).

    Bhadra Mukha is deliberately excluded.
    """

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Bhadra_Type
        FROM Bhadra_Transition
        WHERE Location = ?
          AND Bhadra_Type = 'Bhadra_Puccha'
          AND Start_Date_Time_Local < ?
          AND End_Date_Time_Local > ?
        ORDER BY Start_Date_Time_Local
        """,
        (
            LOCATION,
            end.isoformat(),
            start.isoformat(),
        ),
    ).fetchall()

    return rows


# ============================================================
# Find Masa information
# ============================================================

def get_masa_information(
    conn,
    purnima_start,
):
    """
    Find Masa_Transition containing the beginning of
    Phalguna Purnima.
    """

    row = conn.execute(
        """
        SELECT
            Masa_Number,
            Masa_English,
            Masa_Hindi,
            Masa_Type
        FROM Masa_Transition
        WHERE Location = ?
          AND Start_Date_Time_Local <= ?
          AND End_Date_Time_Local > ?
        ORDER BY Start_Date_Time_Local DESC
        LIMIT 1
        """,
        (
            LOCATION,
            purnima_start.isoformat(),
            purnima_start.isoformat(),
        ),
    ).fetchone()

    return row


# ============================================================
# Determine Holika timing
# ============================================================

def determine_holika_timing(
    conn,
    candidate_start,
    candidate_end,
):
    """
    Apply the finalized Holika Dahan rules.

    Candidate:

        Phalguna Purnima ∩ Pradosh

    Rules:

    1. If there is no Bhadra:
           use the complete candidate.

    2. If Bhadra ends during the candidate:
           perform Holika after Bhadra.

    3. If Bhadra extends beyond the candidate:
           Bhadra continues beyond the Pradosh candidate.

           If Bhadra Puccha occurs DURING the candidate,
           use the Puccha portion.

           Bhadra Mukha is never selected.

           If there is no Puccha during the candidate,
           retain the Pradosh candidate.

    4. The candidate itself is always constrained to
       Purnima ∩ Pradosh.
    """

    bhadra_rows = get_bhadra_overlaps(
        conn,
        candidate_start,
        candidate_end,
    )

    # --------------------------------------------------------
    # CASE 1: No Bhadra
    # --------------------------------------------------------

    if not bhadra_rows:

        return {
            "holika_start": candidate_start,
            "holika_end": candidate_end,
            "bhadra_start": None,
            "bhadra_end": None,
            "reason": "No_Bhadra",
        }

    # --------------------------------------------------------
    # We normally expect one Bhadra interval.
    # --------------------------------------------------------

    (
        bhadra_start_string,
        bhadra_end_string,
        karana_number,
        karana,
    ) = bhadra_rows[0]

    bhadra_start = parse_dt(
        bhadra_start_string
    )

    bhadra_end = parse_dt(
        bhadra_end_string
    )

    # --------------------------------------------------------
    # CASE 2:
    #
    # Bhadra ends inside the Holika candidate.
    #
    # Perform after Bhadra.
    # --------------------------------------------------------

    if (
        bhadra_start <= candidate_start
        and
        candidate_start < bhadra_end < candidate_end
    ):

        return {
            "holika_start": bhadra_end,
            "holika_end": candidate_end,
            "bhadra_start": bhadra_start,
            "bhadra_end": bhadra_end,
            "reason": "After_Bhadra",
        }

    # --------------------------------------------------------
    # CASE 3:
    #
    # Bhadra starts during candidate and continues beyond it.
    #
    # Search Puccha inside the candidate.
    # --------------------------------------------------------

    puccha_rows = get_bhadra_puccha(
        conn,
        candidate_start,
        candidate_end,
    )

    for (
        puccha_start_string,
        puccha_end_string,
        puccha_type,
    ) in puccha_rows:

        puccha_start = parse_dt(
            puccha_start_string
        )

        puccha_end = parse_dt(
            puccha_end_string
        )

        puccha_overlap = get_intersection(
            candidate_start,
            candidate_end,
            puccha_start,
            puccha_end,
        )

        if puccha_overlap is not None:

            (
                holika_start,
                holika_end,
            ) = puccha_overlap

            return {
                "holika_start": holika_start,
                "holika_end": holika_end,
                "bhadra_start": bhadra_start,
                "bhadra_end": bhadra_end,
                "reason": "Bhadra_Puccha",
            }

    # --------------------------------------------------------
    # CASE 4:
    #
    # Bhadra covers candidate and no Puccha is available
    # inside the candidate.
    #
    # Retain the Pradosh candidate.
    # --------------------------------------------------------

    return {
        "holika_start": candidate_start,
        "holika_end": candidate_end,
        "bhadra_start": bhadra_start,
        "bhadra_end": bhadra_end,
        "reason": "Pradosh_No_Puccha",
    }


# ============================================================
# Insert Holika_Holi row
# ============================================================

def insert_holika_row(
    conn,
    holika_start,
    holika_end,
    holi_date,
    masa_number,
    masa_english,
    masa_hindi,
    masa_type,
    tithi,
    paksha,
    purnima_start,
    purnima_end,
    sunset_local,
    pradosh_start,
    pradosh_end,
    bhadra_start,
    bhadra_end,
):
    """
    Insert or replace one Holika_Holi row.
    """

    holika_date = holika_start.date().isoformat()

    conn.execute(
        """
        INSERT OR REPLACE INTO Holika_Holi (
            Date,

            Holika_Dahan_Date_Time_Start_UTC,
            Holika_Dahan_Date_Time_End_UTC,

            Holika_Dahan_Date_Time_Start_Local,
            Holika_Dahan_Date_Time_End_Local,

            Holi_Date,

            Location,
            Latitude,
            Longitude,

            Masa_Number,
            Masa_English,
            Masa_Hindi,
            Masa_Type,

            Tithi,
            Paksha,

            Purnima_Start_Local,
            Purnima_End_Local,

            Sunset_Local,

            Pradosh_Start_Local,
            Pradosh_End_Local,

            Bhadra_Start_Local,
            Bhadra_End_Local
        )
        VALUES (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            holika_date,

            to_utc_string(holika_start),
            to_utc_string(holika_end),

            to_local_string(holika_start),
            to_local_string(holika_end),

            holi_date,

            LOCATION,
            LATITUDE,
            LONGITUDE,

            masa_number,
            masa_english,
            masa_hindi,
            masa_type,

            tithi,
            paksha,

            purnima_start,
            purnima_end,

            sunset_local,

            pradosh_start,
            pradosh_end,

            (
                bhadra_start.isoformat()
                if bhadra_start is not None
                else None
            ),

            (
                bhadra_end.isoformat()
                if bhadra_end is not None
                else None
            ),
        ),
    )


# ============================================================
# Process one year
# ============================================================

def process_year(conn, year):
    """
    Process one calendar year.
    """

    print()
    print("=" * 80)
    print(f"Processing {year}")
    print("=" * 80)

    # --------------------------------------------------------
    # 1. Find Phalguna Purnima and the Pradosh that actually
    #    overlaps it.
    # --------------------------------------------------------

    result = get_phalguna_purnima_pradosh(
        conn,
        year,
    )

    if result is None:

        print(
            f"No Phalguna Purnima/Pradosh overlap found "
            f"for {year}"
        )

        return False

    purnima_start_string = (
        result["purnima_start_string"]
    )

    purnima_end_string = (
        result["purnima_end_string"]
    )

    purnima_start = (
        result["purnima_start"]
    )

    purnima_end = (
        result["purnima_end"]
    )

    pradosh_start = (
        result["pradosh_start"]
    )

    pradosh_end = (
        result["pradosh_end"]
    )

    tithi = result["tithi"]
    paksha = result["paksha"]

    # --------------------------------------------------------
    # 2. Holika candidate =
    #
    #       Purnima ∩ Pradosh
    # --------------------------------------------------------

    candidate = get_intersection(
        purnima_start,
        purnima_end,
        pradosh_start,
        pradosh_end,
    )

    if candidate is None:

        print(
            "ERROR: Purnima/Pradosh overlap disappeared."
        )

        return False

    candidate_start, candidate_end = candidate

    print()
    print("Phalguna Purnima")
    print(
        f"  {purnima_start.isoformat()}"
        f" -> "
        f"{purnima_end.isoformat()}"
    )

    print()
    print("Selected Pradosh")
    print(
        f"  {pradosh_start.isoformat()}"
        f" -> "
        f"{pradosh_end.isoformat()}"
    )

    print()
    print("Holika Candidate = Purnima ∩ Pradosh")
    print(
        f"  {candidate_start.isoformat()}"
        f" -> "
        f"{candidate_end.isoformat()}"
    )

    # --------------------------------------------------------
    # 3. Apply Bhadra rules.
    # --------------------------------------------------------

    timing = determine_holika_timing(
        conn,
        candidate_start,
        candidate_end,
    )

    holika_start = timing["holika_start"]
    holika_end = timing["holika_end"]

    bhadra_start = timing["bhadra_start"]
    bhadra_end = timing["bhadra_end"]

    reason = timing["reason"]

    print()
    print("Final Holika Rule")
    print(f"  Reason : {reason}")
    print(
        f"  Holika : "
        f"{holika_start.isoformat()}"
        f" -> "
        f"{holika_end.isoformat()}"
    )

    if bhadra_start is not None:

        print()
        print("Complete Bhadra")
        print(
            f"  {bhadra_start.isoformat()}"
            f" -> "
            f"{bhadra_end.isoformat()}"
        )

    # --------------------------------------------------------
    # 4. Masa information.
    # --------------------------------------------------------

    masa = get_masa_information(
        conn,
        purnima_start,
    )

    if masa is None:

        raise RuntimeError(
            f"No Masa_Transition row found for "
            f"{purnima_start.isoformat()}"
        )

    (
        masa_number,
        masa_english,
        masa_hindi,
        masa_type,
    ) = masa

    # --------------------------------------------------------
    # 5. Holi = civil date following Holika Dahan date.
    # --------------------------------------------------------

    holika_date = holika_start.date()

    holi_date = (
        holika_date + timedelta(days=1)
    ).isoformat()

    # --------------------------------------------------------
    # 6. Sunset on Holika Dahan date.
    #
    # Sun_Position contains time-only values.
    # --------------------------------------------------------

    holika_date_string = (
        holika_date.isoformat()
    )

    _, sunset_time = get_sun_times(
        conn,
        holika_date_string,
    )

    sunset_local = (
        f"{holika_date_string}"
        f"T{sunset_time.time().isoformat()}"
    )

    # --------------------------------------------------------
    # 7. Insert row.
    # --------------------------------------------------------

    insert_holika_row(
        conn=conn,

        holika_start=holika_start,
        holika_end=holika_end,

        holi_date=holi_date,

        masa_number=masa_number,
        masa_english=masa_english,
        masa_hindi=masa_hindi,
        masa_type=masa_type,

        tithi=tithi,
        paksha=paksha,

        purnima_start=purnima_start_string,
        purnima_end=purnima_end_string,

        sunset_local=sunset_local,

        pradosh_start=pradosh_start.isoformat(),
        pradosh_end=pradosh_end.isoformat(),

        bhadra_start=bhadra_start,
        bhadra_end=bhadra_end,

    )

    print()
    print("Holika_Holi row inserted:")
    print(
        f"  Date      : {holika_date_string}"
    )
    print(
        f"  Holika    : "
        f"{holika_start.isoformat()}"
        f" -> "
        f"{holika_end.isoformat()}"
    )
    print(
        f"  Holi Date : {holi_date}"
    )

    return True


# ============================================================
# Main
# ============================================================

def main():

    conn = get_connection()

    inserted = 0
    skipped = 0

    try:

        for year in range(
            START_YEAR,
            END_YEAR + 1,
        ):

            if process_year(
                conn,
                year,
            ):
                inserted += 1
            else:
                skipped += 1

        conn.commit()

        print()
        print("=" * 80)
        print("Holika_Holi population completed.")
        print("=" * 80)

        print(
            f"Years processed : "
            f"{END_YEAR - START_YEAR + 1}"
        )

        print(
            f"Rows inserted   : {inserted}"
        )

        print(
            f"Years skipped   : {skipped}"
        )

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# ============================================================
# Run
# ============================================================

if __name__ == "__main__":
    main()
