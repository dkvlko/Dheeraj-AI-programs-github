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

KARTIKA_MASA = "08"
DWITIYA_TITHI = "02"
PAKSHA = "Shukla"

# Search around the beginning of Kartika Masa.
# This handles cases where Dwitiya is immediately around
# the Masa boundary.
DWITIYA_SEARCH_DAYS = 4


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
    Parse all datetime formats used in the database.

    Full datetime examples:

        2026-11-09T12:32:07.100042+05:30
        2026-11-09T12:32:07+05:30

    Time-only examples from Sun_Position:

        06:20:40
        17:19:32
        06:20:40.123456

    Time-only values require 'date'.
    """

    value = value.strip()

    # --------------------------------------------------------
    # Full datetime
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
            f"Date required for time-only value: {value}"
        )

    if isinstance(date, datetime):
        date = date.date()

    elif isinstance(date, str):
        date = datetime.strptime(
            date,
            "%Y-%m-%d"
        ).date()

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

            return datetime.combine(
                date,
                time_value
            ).replace(
                tzinfo=TIMEZONE
            )

        except ValueError:
            continue

    raise ValueError(
        f"Unsupported time/datetime format: {value}"
    )


def format_local(dt):
    """
    Return timezone-aware ISO-8601 local datetime.
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
# DWITIYA TRANSITIONS
# ============================================================

def get_dwitiya_candidates():

    """
    Retrieve all Shukla Dwitiya transitions.

    Datetime filtering is deliberately done in Python so that
    timezone-aware and timezone-naive database values never
    get compared directly.
    """

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
            DWITIYA_TITHI,
            PAKSHA,
        ),
    ).fetchall()

    return rows


def select_kartika_dwitiya(
    masa_start,
    masa_end,
):
    """
    Find the Shukla Dwitiya associated with Kartika Masa.

    We search +/- DWITIYA_SEARCH_DAYS around the beginning of
    Kartika and choose the interval closest to that boundary.

    This avoids assuming that Dwitiya must be wholly contained
    inside the Masa_Transition interval.
    """

    window_start = (
        masa_start -
        timedelta(days=DWITIYA_SEARCH_DAYS)
    )

    window_end = (
        masa_start +
        timedelta(days=DWITIYA_SEARCH_DAYS)
    )

    candidates = []

    for row in get_dwitiya_candidates():

        start = parse_local(
            row["Start_Date_Time_Local"]
        )

        end = parse_local(
            row["End_Date_Time_Local"]
        )

        # Does the Dwitiya interval intersect the search window?
        if (
            start < window_end
            and
            end > window_start
        ):

            # Distance from Masa start to Dwitiya interval.
            if masa_start < start:
                distance = (
                    start - masa_start
                )

            elif masa_start > end:
                distance = (
                    masa_start - end
                )

            else:
                distance = timedelta(0)

            candidates.append(
                (
                    distance,
                    start,
                    end,
                    row,
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    return candidates[0][3]


# ============================================================
# SUNRISE / SUNSET
# ============================================================

def get_sun_times(date):

    date_string = date.strftime(
        "%Y-%m-%d"
    )

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
            f"No Sun_Position row found for "
            f"{date_string}"
        )

    # Sun_Position contains time-only values.
    # Combine each value with its Date.

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
# APARAHNA
# ============================================================

def calculate_aparahna(date):

    """
    Divide daylight into five equal parts.

        1st part = sunrise -> 1/5 daylight
        2nd part
        3rd part
        4th part = Aparahna
        5th part

    Therefore:

        Aparahna start =
            sunrise + 3/5 daylight

        Aparahna end =
            sunrise + 4/5 daylight
    """

    sunrise, sunset = get_sun_times(
        date
    )

    daylight = (
        sunset - sunrise
    )

    one_day_part = (
        daylight / 5
    )

    aparahna_start = (
        sunrise +
        3 * one_day_part
    )

    aparahna_end = (
        sunrise +
        4 * one_day_part
    )

    return (
        aparahna_start,
        aparahna_end,
        sunrise,
        sunset,
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
# TITHI AT SUNRISE
# ============================================================

def tithi_at_sunrise(
    tithi_start,
    tithi_end,
    sunrise,
):

    return (
        tithi_start <= sunrise
        <
        tithi_end
    )


# ============================================================
# CALCULATE BHAI DOOJ
# ============================================================

def calculate_bhai_dooj(year):

    # --------------------------------------------------------
    # Find Kartika Masa.
    # --------------------------------------------------------

    masa_row = get_kartika_start(
        year
    )

    if masa_row is None:
        raise RuntimeError(
            f"Could not find Kartika Masa "
            f"transition for {year}"
        )

    masa_start = parse_local(
        masa_row[
            "Start_Date_Time_Local"
        ]
    )

    masa_end = parse_local(
        masa_row[
            "End_Date_Time_Local"
        ]
    )

    print()
    print("=" * 72)
    print(
        f"YEAR: {year}"
    )
    print("=" * 72)

    print(
        "Kartika Masa start:",
        format_local(masa_start)
    )

    print(
        "Kartika Masa end:",
        format_local(masa_end)
    )

    print(
        "Masa:",
        masa_row["Masa_Number"],
        masa_row["Masa_English"],
        masa_row["Masa_Hindi"],
        masa_row["Masa_Type"],
    )

    # --------------------------------------------------------
    # Find Kartika Shukla Dwitiya.
    # --------------------------------------------------------

    dwitiya_row = select_kartika_dwitiya(
        masa_start,
        masa_end,
    )

    if dwitiya_row is None:

        raise RuntimeError(
            f"Could not find Kartika Shukla "
            f"Dwitiya near Kartika start "
            f"for {year}"
        )

    dwitiya_start = parse_local(
        dwitiya_row[
            "Start_Date_Time_Local"
        ]
    )

    dwitiya_end = parse_local(
        dwitiya_row[
            "End_Date_Time_Local"
        ]
    )

    print()
    print(
        "Selected Shukla Dwitiya:",
        format_local(dwitiya_start),
        "->",
        format_local(dwitiya_end),
    )

    # --------------------------------------------------------
    # Civil dates touched by Dwitiya.
    # --------------------------------------------------------

    candidate_dates = sorted(
        {
            dwitiya_start.date(),
            dwitiya_end.date(),
        }
    )

    print()
    print(
        "Candidate civil dates:"
    )

    for date in candidate_dates:
        print(
            " ",
            date
        )

    # --------------------------------------------------------
    # PRIMARY RULE:
    #
    # Dwitiya must prevail during Aparahna.
    #
    # If both dates qualify, select earlier date.
    # --------------------------------------------------------

    qualifying_dates = []

    print()
    print(
        "Aparahna evaluation:"
    )

    for date in candidate_dates:

        (
            aparahna_start,
            aparahna_end,
            sunrise,
            sunset,
        ) = calculate_aparahna(
            date
        )

        overlaps = interval_overlaps(
            dwitiya_start,
            dwitiya_end,
            aparahna_start,
            aparahna_end,
        )

        print()
        print(
            f"Date: {date}"
        )

        print(
            "  Sunrise:",
            format_local(sunrise)
        )

        print(
            "  Sunset:",
            format_local(sunset)
        )

        print(
            "  Aparahna:",
            format_local(
                aparahna_start
            ),
            "->",
            format_local(
                aparahna_end
            ),
        )

        print(
            "  Dwitiya during Aparahna:",
            "YES" if overlaps else "NO"
        )

        if overlaps:
            qualifying_dates.append(
                date
            )

    # --------------------------------------------------------
    # PRIMARY RESULT
    # --------------------------------------------------------

    if qualifying_dates:

        bhai_dooj_date = min(
            qualifying_dates
        )

        rule_applied = (
            "Kartik Shukla Dwitiya prevails "
            "during Aparahna; earlier qualifying "
            "civil date selected"
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    else:

        sunrise_dates = []

        print()
        print(
            "No Aparahna overlap found."
        )

        print(
            "Applying sunrise fallback:"
        )

        for date in candidate_dates:

            (
                aparahna_start,
                aparahna_end,
                sunrise,
                sunset,
            ) = calculate_aparahna(
                date
            )

            qualifies = tithi_at_sunrise(
                dwitiya_start,
                dwitiya_end,
                sunrise,
            )

            print(
                f"  {date}: "
                f"Dwitiya at sunrise = "
                f"{'YES' if qualifies else 'NO'}"
            )

            if qualifies:
                sunrise_dates.append(
                    date
                )

        if sunrise_dates:

            bhai_dooj_date = min(
                sunrise_dates
            )

            rule_applied = (
                "Fallback: Dwitiya did not "
                "prevail during Aparahna; "
                "earlier civil date with "
                "Dwitiya prevailing at sunrise "
                "selected"
            )

        else:

            raise RuntimeError(
                f"Could not determine Bhai Dooj "
                f"date for {year}"
            )

    # --------------------------------------------------------
    # Final Aparahna for selected date.
    # --------------------------------------------------------

    (
        aparahna_start,
        aparahna_end,
        sunrise,
        sunset,
    ) = calculate_aparahna(
        bhai_dooj_date
    )

    print()
    print(
        "SELECTED BHAI DOOJ DATE:"
    )

    print(
        " ",
        bhai_dooj_date
    )

    print()
    print(
        "Final values:"
    )

    print(
        "  Dwitiya:",
        format_local(
            dwitiya_start
        ),
        "->",
        format_local(
            dwitiya_end
        ),
    )

    print(
        "  Aparahna:",
        format_local(
            aparahna_start
        ),
        "->",
        format_local(
            aparahna_end
        ),
    )

    print(
        "  Rule:",
        rule_applied
    )

    return {
        "Date":
            bhai_dooj_date.strftime(
                "%Y-%m-%d"
            ),

        "Location":
            LOCATION,

        "Dwitiya_Start_Local":
            format_local(
                dwitiya_start
            ),

        "Dwitiya_End_Local":
            format_local(
                dwitiya_end
            ),

        "Aparahna_Start_Local":
            format_local(
                aparahna_start
            ),

        "Aparahna_End_Local":
            format_local(
                aparahna_end
            ),

        "Rule_Applied":
            rule_applied,
    }


# ============================================================
# CREATE TABLE
# ============================================================

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS Bhai_Dooj (
        Date TEXT NOT NULL,
        Location TEXT NOT NULL,
        Dwitiya_Start_Local TEXT NOT NULL,
        Dwitiya_End_Local TEXT NOT NULL,
        Aparahna_Start_Local TEXT NOT NULL,
        Aparahna_End_Local TEXT NOT NULL,
        Rule_Applied TEXT NOT NULL,
        PRIMARY KEY (Date, Location)
    )
    """
)

conn.commit()


# ============================================================
# GENERATE AND INSERT
# ============================================================

results = []

for year in range(
    START_YEAR,
    END_YEAR + 1
):

    try:

        result = calculate_bhai_dooj(
            year
        )

        results.append(
            result
        )

        cur.execute(
            """
            INSERT OR REPLACE INTO Bhai_Dooj (
                Date,
                Location,
                Dwitiya_Start_Local,
                Dwitiya_End_Local,
                Aparahna_Start_Local,
                Aparahna_End_Local,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["Date"],
                result["Location"],
                result[
                    "Dwitiya_Start_Local"
                ],
                result[
                    "Dwitiya_End_Local"
                ],
                result[
                    "Aparahna_Start_Local"
                ],
                result[
                    "Aparahna_End_Local"
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
print(
    "BHAI DOOJ SUMMARY"
)
print("=" * 72)

for result in results:

    print(
        result["Date"],
        "|",
        result[
            "Dwitiya_Start_Local"
        ],
        "->",
        result[
            "Dwitiya_End_Local"
        ],
        "|",
        result[
            "Aparahna_Start_Local"
        ],
        "->",
        result[
            "Aparahna_End_Local"
        ],
    )


# ============================================================
# CLOSE
# ============================================================

conn.close()
