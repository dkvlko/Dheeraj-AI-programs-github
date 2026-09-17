#!/usr/bin/env python3

import sqlite3
from datetime import datetime, timedelta
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

KARTIKA_MASA = "08"

# Search this many days on either side of the Kartika
# Masa transition.
AMAVASYA_SEARCH_DAYS = 3


# ============================================================
# DATABASE
# ============================================================

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()


# ============================================================
# DATETIME HELPERS
# ============================================================


def parse_local(value, date=None):
    """
    Permanently handle all datetime formats used by the database.

    Supported examples:

        2026-11-09T12:32:07.100042+05:30
        2026-11-09T12:32:07+05:30
        2026-11-09T12:32:07
        06:20:40
        06:20:40.123456
        06:20:40+05:30

    If only a time is supplied, 'date' MUST be supplied.
    The time is then combined with that civil date and assigned
    Asia/Kolkata when no timezone is present.
    """

    value = value.strip()

    # --------------------------------------------------------
    # Full ISO datetime
    # --------------------------------------------------------

    if "T" in value or " " in value:

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=TIMEZONE
            )
        else:
            dt = dt.astimezone(
                TIMEZONE
            )

        return dt

    # --------------------------------------------------------
    # Time-only value
    # --------------------------------------------------------

    if date is None:
        raise ValueError(
            f"A date is required for time-only value: {value}"
        )

    # date can be:
    #
    #   datetime.date
    #   datetime.datetime
    #   YYYY-MM-DD string
    #

    if isinstance(date, datetime):
        date_value = date.date()

    elif isinstance(date, str):
        date_value = datetime.strptime(
            date,
            "%Y-%m-%d"
        ).date()

    else:
        date_value = date

    # --------------------------------------------------------
    # Try time with timezone first.
    # --------------------------------------------------------

    try:

        time_value = datetime.fromisoformat(
            f"2000-01-01T{value}"
        ).time()

        dt = datetime.combine(
            date_value,
            time_value
        )

        return dt.replace(
            tzinfo=TIMEZONE
        )

    except ValueError:

        # ----------------------------------------------------
        # Pure HH:MM:SS / HH:MM:SS.microseconds
        # ----------------------------------------------------

        from datetime import time

        for fmt in (
            "%H:%M:%S.%f",
            "%H:%M:%S",
            "%H:%M",
        ):

            try:

                time_value = datetime.strptime(
                    value,
                    fmt
                ).time()

                dt = datetime.combine(
                    date_value,
                    time_value
                )

                return dt.replace(
                    tzinfo=TIMEZONE
                )

            except ValueError:
                continue

        raise ValueError(
            f"Unsupported datetime/time format: {value}"
        )


def format_local(dt):
    """
    Return a timezone-aware ISO-8601 local datetime.
    """

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=TIMEZONE
        )
    else:
        dt = dt.astimezone(
            TIMEZONE
        )

    return dt.isoformat()

# ============================================================
# KARTIKA MASA
# ============================================================

def get_kartika_start(year):

    row = cur.execute(
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
          AND substr(Start_Date_Time_Local, 1, 4) = ?
        ORDER BY Start_Date_Time_Local
        LIMIT 1
        """,
        (
            LOCATION,
            KARTIKA_MASA,
            str(year),
        ),
    ).fetchone()

    return row


# ============================================================
# AMAVASYA SEARCH
# ============================================================

def get_amavasya_candidates(masa_start):

    """
    Retrieve Krishna Amavasya transitions and select candidates
    within +/- AMAVASYA_SEARCH_DAYS of Kartika Masa start.

    We deliberately do the datetime comparison in Python so
    timezone-naive and timezone-aware SQLite values cannot be
    compared directly.
    """

    window_start = masa_start - timedelta(
        days=AMAVASYA_SEARCH_DAYS
    )

    window_end = masa_start + timedelta(
        days=AMAVASYA_SEARCH_DAYS
    )

    rows = cur.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Tithi,
            Paksha
        FROM Tithi_Transition
        WHERE Location = ?
          AND Tithi = '15'
          AND Paksha = 'Krishna'
        ORDER BY Start_Date_Time_Local
        """,
        (LOCATION,),
    ).fetchall()

    candidates = []

    for row in rows:

        start = parse_local(
            row["Start_Date_Time_Local"]
        )

        end = parse_local(
            row["End_Date_Time_Local"]
        )

        # Candidate if its interval intersects the search window.
        if start < window_end and end > window_start:
            candidates.append(row)

    return candidates


# ============================================================
# INTERVAL DISTANCE
# ============================================================

def interval_distance_to_point(start, end, point):

    """
    Return distance between an interval and a point.

    If point lies inside interval, distance = zero.
    """

    if start <= point <= end:
        return timedelta(0)

    if point < start:
        return start - point

    return point - end


# ============================================================
# SELECT DIWALI AMAVASYA
# ============================================================

def select_kartika_amavasya(masa_start):

    candidates = get_amavasya_candidates(
        masa_start
    )

    if not candidates:
        return None

    ranked = []

    for row in candidates:

        start = parse_local(
            row["Start_Date_Time_Local"]
        )

        end = parse_local(
            row["End_Date_Time_Local"]
        )

        distance = interval_distance_to_point(
            start,
            end,
            masa_start,
        )

        ranked.append(
            (
                distance,
                start,
                end,
                row,
            )
        )

    # Nearest Amavasya interval to Kartika Masa start.
    ranked.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    return ranked[0][3]


# ============================================================
# SUNRISE / SUNSET
# ============================================================

def get_sun_times(date):

    date_string = date.strftime("%Y-%m-%d")

    row = cur.execute(
        """
        SELECT
            Date,
            Sunrise_Time,
            Sunset_Time
        FROM Sun_Position
        WHERE Date = ?
          AND Location = ?
        LIMIT 1
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

    sunrise = parse_local(
        row["Sunrise_Time"],
        row["Date"]
    )

    sunset = parse_local(
        row["Sunset_Time"],
        row["Date"]
    )

    return sunrise, sunset


# ============================================================
# PRADOSHA
# ============================================================

def calculate_pradosha(date):

    """
    Pradosha Kaal:

        Start = today's sunset

        End = today's sunset + 1/5 of the following night

    Following night:

        next sunrise - today's sunset
    """

    sunrise_today, sunset_today = get_sun_times(
        date
    )

    next_date = date + timedelta(days=1)

    sunrise_next, _ = get_sun_times(
        next_date
    )

    night_duration = (
        sunrise_next - sunset_today
    )

    pradosha_duration = (
        night_duration / 5
    )

    pradosha_start = sunset_today

    pradosha_end = (
        sunset_today + pradosha_duration
    )

    return (
        pradosha_start,
        pradosha_end,
        sunrise_today,
        sunset_today,
        sunrise_next,
    )


# ============================================================
# INTERVAL OVERLAP
# ============================================================

def interval_overlaps(
    start1,
    end1,
    start2,
    end2,
):

    return (
        start1 < end2
        and
        end1 > start2
    )


# ============================================================
# AMAVASYA AT SUNSET
# ============================================================

def amavasya_at_sunset(
    amavasya_start,
    amavasya_end,
    sunset,
):

    return (
        amavasya_start <= sunset
        <
        amavasya_end
    )


# ============================================================
# CALCULATE DIWALI
# ============================================================

def calculate_diwali(year):

    masa_row = get_kartika_start(year)

    if masa_row is None:
        raise RuntimeError(
            f"Could not find Kartika Masa transition "
            f"for {year}"
        )

    masa_start = parse_local(
        masa_row["Start_Date_Time_Local"]
    )

    print()
    print("=" * 72)
    print(f"YEAR: {year}")
    print("=" * 72)

    print(
        "Kartika Masa start:",
        format_local(masa_start)
    )

    print(
        "Masa:",
        masa_row["Masa_Number"],
        masa_row["Masa_English"],
        masa_row["Masa_Hindi"],
        masa_row["Masa_Type"],
    )

    # --------------------------------------------------------
    # Find the Amavasya associated with the beginning of
    # Kartika Masa.
    # --------------------------------------------------------

    amavasya_row = select_kartika_amavasya(
        masa_start
    )

    if amavasya_row is None:
        raise RuntimeError(
            f"No Krishna Amavasya found within "
            f"+/- {AMAVASYA_SEARCH_DAYS} days of "
            f"Kartika Masa start for {year}"
        )

    amavasya_start = parse_local(
        amavasya_row["Start_Date_Time_Local"]
    )

    amavasya_end = parse_local(
        amavasya_row["End_Date_Time_Local"]
    )

    print()
    print(
        "Selected Krishna Amavasya:",
        format_local(amavasya_start),
        "->",
        format_local(amavasya_end),
    )

    # --------------------------------------------------------
    # Civil dates touched by Amavasya.
    # --------------------------------------------------------

    candidate_dates = sorted(
        {
            amavasya_start.date(),
            amavasya_end.date(),
        }
    )

    print()
    print("Candidate civil dates:")

    for date in candidate_dates:
        print(" ", date)

    # --------------------------------------------------------
    # PRIMARY RULE:
    #
    # Amavasya must prevail during Pradosha Kaal.
    #
    # If both dates qualify, select earlier date.
    # --------------------------------------------------------

    qualifying_dates = []

    print()
    print("Pradosha evaluation:")

    for date in candidate_dates:

        (
            pradosha_start,
            pradosha_end,
            sunrise_today,
            sunset_today,
            sunrise_next,
        ) = calculate_pradosha(date)

        overlaps = interval_overlaps(
            amavasya_start,
            amavasya_end,
            pradosha_start,
            pradosha_end,
        )

        print()
        print(f"Date: {date}")

        print(
            "  Sunrise:",
            format_local(sunrise_today)
        )

        print(
            "  Sunset:",
            format_local(sunset_today)
        )

        print(
            "  Next sunrise:",
            format_local(sunrise_next)
        )

        print(
            "  Pradosha:",
            format_local(pradosha_start),
            "->",
            format_local(pradosha_end),
        )

        print(
            "  Amavasya during Pradosha:",
            "YES" if overlaps else "NO"
        )

        if overlaps:
            qualifying_dates.append(date)

    # --------------------------------------------------------
    # PRIMARY RESULT
    # --------------------------------------------------------

    if qualifying_dates:

        diwali_date = min(
            qualifying_dates
        )

        rule_applied = (
            "Krishna Amavasya prevails during "
            "Pradosha Kaal; earlier qualifying "
            "civil date selected"
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    else:

        sunset_dates = []

        print()
        print(
            "No Pradosha overlap found."
        )

        print(
            "Applying sunset fallback:"
        )

        for date in candidate_dates:

            (
                pradosha_start,
                pradosha_end,
                sunrise_today,
                sunset_today,
                sunrise_next,
            ) = calculate_pradosha(date)

            qualifies = amavasya_at_sunset(
                amavasya_start,
                amavasya_end,
                sunset_today,
            )

            print(
                f"  {date}: "
                f"Amavasya at sunset = "
                f"{'YES' if qualifies else 'NO'}"
            )

            if qualifies:
                sunset_dates.append(
                    date
                )

        if sunset_dates:

            diwali_date = min(
                sunset_dates
            )

            rule_applied = (
                "Fallback: Krishna Amavasya did not "
                "prevail during Pradosha; earlier civil "
                "date with Amavasya prevailing at sunset "
                "selected"
            )

        else:

            raise RuntimeError(
                f"Could not determine Diwali date "
                f"for {year}"
            )

    # --------------------------------------------------------
    # FINAL PRADOSHA
    # --------------------------------------------------------

    (
        pradosha_start,
        pradosha_end,
        sunrise,
        sunset,
        sunrise_next,
    ) = calculate_pradosha(
        diwali_date
    )

    print()
    print(
        "SELECTED DIWALI DATE:"
    )

    print(
        " ",
        diwali_date
    )

    print()
    print("Final values:")

    print(
        "  Amavasya:",
        format_local(amavasya_start),
        "->",
        format_local(amavasya_end),
    )

    print(
        "  Pradosha:",
        format_local(pradosha_start),
        "->",
        format_local(pradosha_end),
    )

    print(
        "  Rule:",
        rule_applied
    )

    return {
        "Date": diwali_date.strftime(
            "%Y-%m-%d"
        ),
        "Location": LOCATION,
        "Amavasya_Start_Local":
            format_local(amavasya_start),
        "Amavasya_End_Local":
            format_local(amavasya_end),
        "Pradosha_Start_Local":
            format_local(pradosha_start),
        "Pradosha_End_Local":
            format_local(pradosha_end),
        "Rule_Applied":
            rule_applied,
    }


# ============================================================
# CREATE TABLE
# ============================================================

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS Diwali (
        Date TEXT NOT NULL,
        Location TEXT NOT NULL,
        Amavasya_Start_Local TEXT NOT NULL,
        Amavasya_End_Local TEXT NOT NULL,
        Pradosha_Start_Local TEXT NOT NULL,
        Pradosha_End_Local TEXT NOT NULL,
        Rule_Applied TEXT NOT NULL,
        PRIMARY KEY (Date, Location)
    )
    """
)

conn.commit()


# ============================================================
# GENERATE
# ============================================================

results = []

for year in range(
    START_YEAR,
    END_YEAR + 1
):

    try:

        result = calculate_diwali(
            year
        )

        results.append(result)

        cur.execute(
            """
            INSERT OR REPLACE INTO Diwali (
                Date,
                Location,
                Amavasya_Start_Local,
                Amavasya_End_Local,
                Pradosha_Start_Local,
                Pradosha_End_Local,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["Date"],
                result["Location"],
                result[
                    "Amavasya_Start_Local"
                ],
                result[
                    "Amavasya_End_Local"
                ],
                result[
                    "Pradosha_Start_Local"
                ],
                result[
                    "Pradosha_End_Local"
                ],
                result[
                    "Rule_Applied"
                ],
            ),
        )

        conn.commit()

    except Exception as e:

        print()
        print(
            f"ERROR processing {year}: {e}"
        )


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 72)
print("DIWALI SUMMARY")
print("=" * 72)

for result in results:

    print(
        result["Date"],
        "|",
        result[
            "Amavasya_Start_Local"
        ],
        "->",
        result[
            "Amavasya_End_Local"
        ],
        "|",
        result[
            "Pradosha_Start_Local"
        ],
        "->",
        result[
            "Pradosha_End_Local"
        ],
    )


# ============================================================
# CLOSE
# ============================================================

conn.close()
