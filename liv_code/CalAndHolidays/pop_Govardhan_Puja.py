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
PRATIPADA_TITHI = "01"
PAKSHA = "Shukla"


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
    Parse all datetime formats used by the database.

    Full datetime examples:

        2026-11-09T12:32:07.100042+05:30
        2026-11-09T12:32:07+05:30

    Time-only examples from Sun_Position:

        06:20:40
        17:19:32
        06:20:40.123456

    If a time-only value is supplied, 'date' must also be
    supplied so that the time can be converted into a complete
    timezone-aware local datetime.
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

    # Try supported time formats.

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
    Convert datetime to timezone-aware ISO-8601 local string.
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
# SHUKLA PRATIPADA
# ============================================================

def get_pratipada_candidates(year):

    """
    Retrieve all Shukla Pratipada transitions for the year.

    We filter the year in Python after parsing the datetime,
    avoiding dependence on SQLite datetime formatting.
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
            PRATIPADA_TITHI,
            PAKSHA,
        ),
    ).fetchall()

    candidates = []

    for row in rows:

        start = parse_local(
            row["Start_Date_Time_Local"]
        )

        end = parse_local(
            row["End_Date_Time_Local"]
        )

        # Pratipada is associated with Kartika. We don't trust
        # a potentially problematic Masa value in Tithi_Transition;
        # instead the caller will match the transition to Kartika.
        if (
            start.year == year
            or end.year == year
        ):
            candidates.append(
                row
            )

    return candidates


def select_kartika_pratipada(
    year,
    kartika_start,
    kartika_end,
):
    """
    Select the Shukla Pratipada associated with Kartika Masa.

    The Pratipada relevant to Govardhan Puja is the one nearest
    the beginning of Kartika.

    We therefore rank Pratipada intervals by their distance from
    the Kartika Masa start.
    """

    candidates = get_pratipada_candidates(
        year
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

        # Only consider Pratipada reasonably close to Kartika
        # start. A 3-day window handles normal boundary cases.
        window_start = (
            kartika_start -
            timedelta(days=3)
        )

        window_end = (
            kartika_start +
            timedelta(days=3)
        )

        if (
            start < window_end
            and
            end > window_start
        ):

            if kartika_start < start:
                distance = start - kartika_start

            elif kartika_start > end:
                distance = kartika_start - end

            else:
                distance = timedelta(0)

            ranked.append(
                (
                    distance,
                    start,
                    end,
                    row,
                )
            )

    if not ranked:
        return None

    ranked.sort(
        key=lambda x: (
            x[0],
            x[1],
        )
    )

    return ranked[0][3]


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

    # Sunrise_Time and Sunset_Time are stored as time-only
    # values such as 06:20:40.

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
# PRATAHKAAL
# ============================================================

def calculate_pratahkaal(date):

    """
    Pratahkaal = first 1/5 of daylight.

        Daylight = sunset - sunrise

        Pratahkaal duration = daylight / 5

        Pratahkaal =
            sunrise
            ->
            sunrise + daylight/5
    """

    sunrise, sunset = get_sun_times(
        date
    )

    daylight = (
        sunset - sunrise
    )

    pratahkaal_duration = (
        daylight / 5
    )

    pratahkaal_start = sunrise

    pratahkaal_end = (
        sunrise + pratahkaal_duration
    )

    return (
        pratahkaal_start,
        pratahkaal_end,
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
# PRATIPADA AT SUNRISE
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
# CALCULATE GOVARDHAN PUJA
# ============================================================

def calculate_govardhan(year):

    masa_row = get_kartika_start(
        year
    )

    if masa_row is None:
        raise RuntimeError(
            f"Could not find Kartika Masa "
            f"transition for {year}"
        )

    kartika_start = parse_local(
        masa_row[
            "Start_Date_Time_Local"
        ]
    )

    kartika_end = parse_local(
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
        format_local(kartika_start)
    )

    print(
        "Kartika Masa end:",
        format_local(kartika_end)
    )

    print(
        "Masa:",
        masa_row["Masa_Number"],
        masa_row["Masa_English"],
        masa_row["Masa_Hindi"],
        masa_row["Masa_Type"],
    )

    # --------------------------------------------------------
    # Find Kartika Shukla Pratipada.
    # --------------------------------------------------------

    pratipada_row = (
        select_kartika_pratipada(
            year,
            kartika_start,
            kartika_end,
        )
    )

    if pratipada_row is None:

        raise RuntimeError(
            f"Could not find Kartika Shukla "
            f"Pratipada near Kartika start "
            f"for {year}"
        )

    pratipada_start = parse_local(
        pratipada_row[
            "Start_Date_Time_Local"
        ]
    )

    pratipada_end = parse_local(
        pratipada_row[
            "End_Date_Time_Local"
        ]
    )

    print()
    print(
        "Selected Shukla Pratipada:",
        format_local(pratipada_start),
        "->",
        format_local(pratipada_end),
    )

    # --------------------------------------------------------
    # Civil dates touched by Pratipada.
    # --------------------------------------------------------

    candidate_dates = sorted(
        {
            pratipada_start.date(),
            pratipada_end.date(),
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
    # Shukla Pratipada should prevail during Pratahkaal.
    #
    # If both dates qualify, choose earlier date.
    # --------------------------------------------------------

    qualifying_dates = []

    print()
    print(
        "Pratahkaal evaluation:"
    )

    for date in candidate_dates:

        (
            pratahkaal_start,
            pratahkaal_end,
            sunrise,
            sunset,
        ) = calculate_pratahkaal(
            date
        )

        overlaps = interval_overlaps(
            pratipada_start,
            pratipada_end,
            pratahkaal_start,
            pratahkaal_end,
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
            "  Pratahkaal:",
            format_local(
                pratahkaal_start
            ),
            "->",
            format_local(
                pratahkaal_end
            ),
        )

        print(
            "  Pratipada during Pratahkaal:",
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

        govardhan_date = min(
            qualifying_dates
        )

        rule_applied = (
            "Kartik Shukla Pratipada prevails "
            "during Pratahkaal; earlier qualifying "
            "civil date selected"
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    else:

        sunrise_dates = []

        print()
        print(
            "No Pratahkaal overlap found."
        )

        print(
            "Applying sunrise fallback:"
        )

        for date in candidate_dates:

            (
                pratahkaal_start,
                pratahkaal_end,
                sunrise,
                sunset,
            ) = calculate_pratahkaal(
                date
            )

            qualifies = tithi_at_sunrise(
                pratipada_start,
                pratipada_end,
                sunrise,
            )

            print(
                f"  {date}: "
                f"Pratipada at sunrise = "
                f"{'YES' if qualifies else 'NO'}"
            )

            if qualifies:
                sunrise_dates.append(
                    date
                )

        if sunrise_dates:

            govardhan_date = min(
                sunrise_dates
            )

            rule_applied = (
                "Fallback: Pratipada did not "
                "prevail during Pratahkaal; "
                "earlier civil date with "
                "Pratipada prevailing at sunrise "
                "selected"
            )

        else:

            raise RuntimeError(
                f"Could not determine Govardhan "
                f"Puja date for {year}"
            )

    # --------------------------------------------------------
    # Final Pratahkaal for selected date.
    # --------------------------------------------------------

    (
        pratahkaal_start,
        pratahkaal_end,
        sunrise,
        sunset,
    ) = calculate_pratahkaal(
        govardhan_date
    )

    print()
    print(
        "SELECTED GOVARDHAN PUJA DATE:"
    )

    print(
        " ",
        govardhan_date
    )

    print()
    print(
        "Final values:"
    )

    print(
        "  Pratipada:",
        format_local(
            pratipada_start
        ),
        "->",
        format_local(
            pratipada_end
        ),
    )

    print(
        "  Pratahkaal:",
        format_local(
            pratahkaal_start
        ),
        "->",
        format_local(
            pratahkaal_end
        ),
    )

    print(
        "  Rule:",
        rule_applied
    )

    return {
        "Date":
            govardhan_date.strftime(
                "%Y-%m-%d"
            ),

        "Location":
            LOCATION,

        "Pratipada_Start_Local":
            format_local(
                pratipada_start
            ),

        "Pratipada_End_Local":
            format_local(
                pratipada_end
            ),

        "Pratahkaal_Start_Local":
            format_local(
                pratahkaal_start
            ),

        "Pratahkaal_End_Local":
            format_local(
                pratahkaal_end
            ),

        "Rule_Applied":
            rule_applied,
    }


# ============================================================
# CREATE TABLE
# ============================================================

cur.execute(
    """
    CREATE TABLE IF NOT EXISTS Govardhan_Puja (
        Date TEXT NOT NULL,
        Location TEXT NOT NULL,
        Pratipada_Start_Local TEXT NOT NULL,
        Pratipada_End_Local TEXT NOT NULL,
        Pratahkaal_Start_Local TEXT NOT NULL,
        Pratahkaal_End_Local TEXT NOT NULL,
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

        result = calculate_govardhan(
            year
        )

        results.append(
            result
        )

        cur.execute(
            """
            INSERT OR REPLACE INTO Govardhan_Puja (
                Date,
                Location,
                Pratipada_Start_Local,
                Pratipada_End_Local,
                Pratahkaal_Start_Local,
                Pratahkaal_End_Local,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result["Date"],
                result["Location"],
                result[
                    "Pratipada_Start_Local"
                ],
                result[
                    "Pratipada_End_Local"
                ],
                result[
                    "Pratahkaal_Start_Local"
                ],
                result[
                    "Pratahkaal_End_Local"
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
    "GOVARDHAN PUJA SUMMARY"
)
print("=" * 72)

for result in results:

    print(
        result["Date"],
        "|",
        result[
            "Pratipada_Start_Local"
        ],
        "->",
        result[
            "Pratipada_End_Local"
        ],
        "|",
        result[
            "Pratahkaal_Start_Local"
        ],
        "->",
        result[
            "Pratahkaal_End_Local"
        ],
    )


# ============================================================
# CLOSE
# ============================================================

conn.close()
