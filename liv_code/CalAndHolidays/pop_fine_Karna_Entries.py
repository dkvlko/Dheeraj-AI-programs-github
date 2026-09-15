
#!/usr/bin/env python3

"""
Populate Karana_Transition using:

    Sun_Moon_Position
        ↓
3-hour brackets
        ↓
6° angular-separation boundaries
        ↓
Swiss Ephemeris exact root solving
        ↓
Karana_Transition

One Karana = 6° of Moon-Sun angular separation.

Karana positions:

01  Kimstughna
02  Bava
03  Balava
04  Kaulava
05  Taitila
06  Gara
07  Vanija
08  Vishti
09  Bava
...
57  Vishti
58  Shakuni
59  Chatushpada
60  Naga

Vishti is Bhadra.
Therefore positions:
08, 15, 22, 29, 36, 43, 50, 57
have Is_Bhadra = 1.

The source Sun_Moon_Position table is assumed to contain
3-hour observations.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import swisseph as swe


# ============================================================
# CONFIGURATION
# ============================================================

DATABASE_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"

LATITUDE = 26.8467
LONGITUDE = 80.9462

TIMEZONE = ZoneInfo("Asia/Kolkata")

START_DATE = datetime(
    1926, 1, 1, 0, 0, 0,
    tzinfo=timezone.utc
)

END_DATE = datetime(
    2126, 1, 1, 0, 0, 0,
    tzinfo=timezone.utc
)


# Swiss Ephemeris settings
swe.set_sid_mode(swe.SIDM_LAHIRI)

FLAGS = (
    swe.FLG_SWIEPH
    | swe.FLG_SPEED
    | swe.FLG_SIDEREAL
)


# Root-solving precision.
# 1 millisecond in time is considerably more precise
# than needed for a Panchanga transition.
ROOT_TOLERANCE_SECONDS = 0.001


# ============================================================
# KARANA DEFINITIONS
# ============================================================

# Position 01 is fixed.
# Positions 02-57 repeat the following seven Karanas.
# Positions 58-60 are fixed.

MOVABLE_KARANAS = (
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Gara",
    "Vanija",
    "Vishti",
)


def karana_name(karana_number: int) -> str:
    """
    Return the traditional Karana name for position 1-60.
    """

    if karana_number == 1:
        return "Kimstughna"

    if 2 <= karana_number <= 57:
        return MOVABLE_KARANAS[(karana_number - 2) % 7]

    if karana_number == 58:
        return "Shakuni"

    if karana_number == 59:
        return "Chatushpada"

    if karana_number == 60:
        return "Naga"

    raise ValueError(
        f"Invalid Karana number: {karana_number}"
    )


def is_bhadra(karana_number: int) -> int:
    """
    Vishti is Bhadra.

    Vishti occurs at positions:
        08, 15, 22, 29, 36, 43, 50, 57
    """

    return int(
        karana_name(karana_number) == "Vishti"
    )


# ============================================================
# DATETIME HELPERS
# ============================================================

def datetime_to_julian_day(dt_utc: datetime) -> float:
    """
    Convert aware UTC datetime to Julian Day in UT.
    """

    dt_utc = dt_utc.astimezone(timezone.utc)

    hour = (
        dt_utc.hour
        + dt_utc.minute / 60.0
        + dt_utc.second / 3600.0
        + dt_utc.microsecond / 3_600_000_000.0
    )

    return swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        hour,
        swe.GREG_CAL,
    )


def julian_day_to_datetime(jd: float) -> datetime:
    """
    Convert Julian Day to aware UTC datetime.
    """

    year, month, day, hour = swe.revjul(
        jd,
        swe.GREG_CAL,
    )

    hour_int = int(hour)

    minute_float = (hour - hour_int) * 60.0
    minute_int = int(minute_float)

    second_float = (
        minute_float - minute_int
    ) * 60.0

    second_int = int(second_float)

    microsecond = int(
        round(
            (second_float - second_int)
            * 1_000_000
        )
    )

    # Protect against rounding to exactly 1 second.
    if microsecond >= 1_000_000:
        microsecond -= 1_000_000
        second_int += 1

    return datetime(
        year,
        month,
        day,
        hour_int,
        minute_int,
        second_int,
        microsecond,
        tzinfo=timezone.utc,
    )


def format_utc(dt: datetime) -> str:
    """
    ISO-8601 UTC string.
    """

    return (
        dt.astimezone(timezone.utc)
        .isoformat()
    )


def format_local(dt: datetime) -> str:
    """
    ISO-8601 local-time string.
    """

    return (
        dt.astimezone(TIMEZONE)
        .isoformat()
    )


# ============================================================
# SWISS EPHEMERIS
# ============================================================

def get_angular_separation(dt_utc: datetime) -> float:
    """
    Return Moon-Sun sidereal angular separation.

    Result is normalized to [0, 360).
    """

    jd = datetime_to_julian_day(dt_utc)

    sun_result, _ = swe.calc_ut(
        jd,
        swe.SUN,
        FLAGS,
    )

    moon_result, _ = swe.calc_ut(
        jd,
        swe.MOON,
        FLAGS,
    )

    sun_longitude = sun_result[0] % 360.0
    moon_longitude = moon_result[0] % 360.0

    separation = (
        moon_longitude - sun_longitude
    ) % 360.0

    return separation


# ============================================================
# UNWRAPPED ANGULAR SEPARATION
# ============================================================

def forward_difference(
    start: float,
    end: float,
) -> float:
    """
    Return forward angular movement from start to end.

    Example:

        358 -> 2 = 4 degrees
        100 -> 110 = 10 degrees
    """

    return (end - start) % 360.0


def unwrap_next(
    previous_unwrapped: float,
    current_normalized: float,
) -> float:
    """
    Convert a normalized [0,360) value into the next
    continuously increasing angular-separation value.

    Example:

        previous = 358
        current  = 2

        result = 362
    """

    previous_normalized = (
        previous_unwrapped % 360.0
    )

    delta = (
        current_normalized
        - previous_normalized
    ) % 360.0

    return (
        previous_unwrapped
        + delta
    )


# ============================================================
# EXACT ROOT SOLVER
# ============================================================

def separation_error(
    dt_utc: datetime,
    target_unwrapped: float,
    reference_unwrapped: float,
) -> float:
    """
    Calculate:

        current_unwrapped_separation
        - target_unwrapped

    relative to reference_unwrapped.

    This allows us to solve boundaries such as:

        360°
        366°
        372°
        ...

    without problems caused by the 0°/360° wrap.
    """

    current = get_angular_separation(
        dt_utc
    )

    current_unwrapped = unwrap_next(
        reference_unwrapped,
        current,
    )

    return (
        current_unwrapped
        - target_unwrapped
    )


def solve_boundary(
    left_dt: datetime,
    right_dt: datetime,
    left_unwrapped: float,
    target_unwrapped: float,
) -> datetime:
    """
    Find the exact time at which angular separation
    reaches target_unwrapped.

    Bisection is used because the 3-hour source samples
    already provide a valid bracket.

    Precision: ROOT_TOLERANCE_SECONDS.
    """

    left = left_dt
    right = right_dt

    left_value = (
        left_unwrapped
        - target_unwrapped
    )

    # The target must lie between the bracket.
    right_separation = get_angular_separation(
        right
    )

    right_unwrapped = unwrap_next(
        left_unwrapped,
        right_separation,
    )

    right_value = (
        right_unwrapped
        - target_unwrapped
    )

    if left_value > 0:
        raise RuntimeError(
            "Left side is already beyond root."
        )

    if right_value < 0:
        raise RuntimeError(
            "Right side has not reached root."
        )

    while (
        right - left
    ).total_seconds() > ROOT_TOLERANCE_SECONDS:

        middle = left + (
            right - left
        ) / 2

        middle_separation = (
            get_angular_separation(
                middle
            )
        )

        middle_unwrapped = unwrap_next(
            left_unwrapped,
            middle_separation,
        )

        middle_value = (
            middle_unwrapped
            - target_unwrapped
        )

        if middle_value >= 0:
            right = middle
        else:
            left = middle

    return left + (
        right - left
    ) / 2


# ============================================================
# READ SOURCE DATA
# ============================================================

def load_source_rows(
    connection: sqlite3.Connection,
) -> list[tuple[datetime, float]]:
    """
    Load Sun_Moon_Position rows for the requested
    date range and location.

    Returns:

        [(datetime_utc, angular_separation), ...]
    """

    cursor = connection.execute(
        """
        SELECT
            Date_Time_UTC,
            Angular_Separation
        FROM Sun_Moon_Position
        WHERE Location = ?
          AND Date_Time_UTC >= ?
          AND Date_Time_UTC <= ?
        ORDER BY Date_Time_UTC
        """,
        (
            LOCATION,
            format_utc(START_DATE),
            format_utc(END_DATE),
        ),
    )

    rows = []

    for date_time_text, separation in cursor:
        dt = datetime.fromisoformat(
            date_time_text
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        rows.append(
            (
                dt.astimezone(timezone.utc),
                float(separation),
            )
        )

    return rows


# ============================================================
# FIND ALL 6° BOUNDARIES
# ============================================================

def find_boundaries(
    source_rows: list[tuple[datetime, float]],
) -> list[tuple[datetime, float]]:
    """
    Find exact times for every 6° angular-separation
    boundary.

    Returns:

        [
            (boundary_datetime, boundary_angle),
            ...
        ]

    boundary_angle is represented on a continuously
    increasing scale:

        6, 12, 18, ...,
        354, 360, 366, ...

    The actual database value is later normalized
    to 0-360.
    """

    if len(source_rows) < 2:
        raise RuntimeError(
            "Not enough Sun_Moon_Position rows."
        )

    boundaries = []

    previous_dt, previous_sep = source_rows[0]

    previous_unwrapped = previous_sep

    # First 6° boundary after the first source sample.
    next_boundary = (
        math.floor(
            previous_unwrapped / 6.0
        )
        + 1
    ) * 6.0

    for current_dt, current_sep in source_rows[1:]:

        current_unwrapped = unwrap_next(
            previous_unwrapped,
            current_sep,
        )

        # Normally a 3-hour interval advances only
        # about 1.5-2 degrees, so at most one 6°
        # boundary should be crossed.
        #
        # The while loop nevertheless makes the code
        # robust if a larger source interval is used.

        while (
            next_boundary
            <= current_unwrapped
        ):

            exact_dt = solve_boundary(
                previous_dt,
                current_dt,
                previous_unwrapped,
                next_boundary,
            )

            boundaries.append(
                (
                    exact_dt,
                    next_boundary,
                )
            )

            next_boundary += 6.0

        previous_dt = current_dt
        previous_unwrapped = current_unwrapped

    return boundaries


# ============================================================
# CREATE KARANA INTERVALS
# ============================================================

def build_karana_intervals(
    boundaries: list[tuple[datetime, float]],
) -> list[dict]:
    """
    Convert consecutive 6° boundaries into Karana
    intervals.

    For each interval:

        Start = exact 6° boundary
        End   = exact next 6° boundary

    The Karana number is determined from the
    starting angular-separation position.
    """

    intervals = []

    for index in range(
        len(boundaries) - 1
    ):

        start_dt, start_angle = boundaries[index]
        end_dt, end_angle = boundaries[index + 1]

        # The first Karana interval is:
        #
        #   0-6  = position 01
        #   6-12 = position 02
        #
        # Therefore boundary 6° corresponds to
        # Karana 02.
        #
        # Since our first boundary may be 6°, the
        # position is:
        #
        #   angle / 6 + 1
        #
        # with 360° wrapping to position 61 -> 01.
        #
        # Use modulo 60.

        start_position = (
            int(
                round(start_angle / 6.0)
            ) % 60
        ) + 1

        # 360° should correspond to the beginning
        # of Karana 01.
        if start_position == 61:
            start_position = 1

        name = karana_name(
            start_position
        )

        intervals.append(
            {
                "start_dt": start_dt,
                "end_dt": end_dt,

                "start_angle": (
                    start_angle % 360.0
                ),

                "end_angle": (
                    end_angle % 360.0
                ),

                "karana_number": (
                    f"{start_position:02d}"
                ),

                "karana": name,

                "is_bhadra": is_bhadra(
                    start_position
                ),
            }
        )

    return intervals


# ============================================================
# DATABASE INSERT
# ============================================================

def write_database(
    connection: sqlite3.Connection,
    intervals: list[dict],
) -> None:
    """
    Delete the existing Karana_Transition data for this
    location and rebuild it.
    """

    connection.execute(
        """
        DELETE FROM Karana_Transition
        WHERE Location = ?
        """,
        (LOCATION,),
    )

    insert_sql = """
        INSERT INTO Karana_Transition (
            Start_Date_Time_UTC,
            End_Date_Time_UTC,

            Start_Date_Time_Local,
            End_Date_Time_Local,

            Location,

            Angular_Separation_Start,
            Angular_Separation_End,

            Karana_Number,
            Karana,

            Is_Bhadra
        )
        VALUES (
            ?, ?,
            ?, ?,
            ?,
            ?, ?,
            ?, ?,
            ?
        )
    """

    rows = []

    for item in intervals:

        rows.append(
            (
                format_utc(
                    item["start_dt"]
                ),
                format_utc(
                    item["end_dt"]
                ),

                format_local(
                    item["start_dt"]
                ),
                format_local(
                    item["end_dt"]
                ),

                LOCATION,

                item["start_angle"],
                item["end_angle"],

                item["karana_number"],
                item["karana"],

                item["is_bhadra"],
            )
        )

    connection.executemany(
        insert_sql,
        rows,
    )

    connection.commit()


# ============================================================
# VALIDATION
# ============================================================

def validate(
    connection: sqlite3.Connection,
) -> None:
    """
    Perform basic consistency checks.
    """

    print()
    print("=" * 70)
    print("VALIDATION")
    print("=" * 70)

    cursor = connection.execute(
        """
        SELECT COUNT(*)
        FROM Karana_Transition
        WHERE Location = ?
        """,
        (LOCATION,),
    )

    count = cursor.fetchone()[0]

    print(
        f"Karana_Transition rows: {count:,}"
    )

    # --------------------------------------------------------
    # Check invalid Karana numbers
    # --------------------------------------------------------

    cursor = connection.execute(
        """
        SELECT
            Karana_Number,
            Karana,
            COUNT(*)
        FROM Karana_Transition
        WHERE Location = ?
        GROUP BY Karana_Number, Karana
        ORDER BY CAST(Karana_Number AS INTEGER)
        """,
        (LOCATION,),
    )

    print()
    print("Karana distribution:")

    for number, name, count in cursor:
        print(
            f"  {number}  {name:<12} {count:,}"
        )

    # --------------------------------------------------------
    # Check Bhadra
    # --------------------------------------------------------

    cursor = connection.execute(
        """
        SELECT
            Karana_Number,
            Karana,
            COUNT(*)
        FROM Karana_Transition
        WHERE Location = ?
          AND Is_Bhadra = 1
        GROUP BY Karana_Number, Karana
        ORDER BY CAST(Karana_Number AS INTEGER)
        """,
        (LOCATION,),
    )

    print()
    print("Bhadra / Vishti positions:")

    for number, name, count in cursor:
        print(
            f"  {number}  {name:<12} {count:,}"
        )

    # --------------------------------------------------------
    # Check zero/negative intervals
    # --------------------------------------------------------

    cursor = connection.execute(
        """
        SELECT COUNT(*)
        FROM Karana_Transition
        WHERE Location = ?
          AND Start_Date_Time_UTC
              >= End_Date_Time_UTC
        """,
        (LOCATION,),
    )

    invalid = cursor.fetchone()[0]

    print()
    print(
        f"Invalid time intervals: {invalid}"
    )

    # --------------------------------------------------------
    # Check angular interval sizes
    # --------------------------------------------------------

    cursor = connection.execute(
        """
        SELECT COUNT(*)
        FROM Karana_Transition
        WHERE Location = ?
          AND (
              ABS(
                  (
                      (Angular_Separation_End
                       - Angular_Separation_Start)
                      + 360.0
                  )
                  % 360.0
              ) < 5.999
          )
        """,
        (LOCATION,),
    )

    bad_angle_count = cursor.fetchone()[0]

    print(
        "Intervals with suspicious angular "
        f"width: {bad_angle_count}"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print("=" * 70)
    print("KARANA TRANSITION GENERATOR")
    print("=" * 70)

    print()
    print(f"Database : {DATABASE_PATH}")
    print(f"Location : {LOCATION}")
    print(
        f"Period   : "
        f"{START_DATE.isoformat()} "
        f"to "
        f"{END_DATE.isoformat()}"
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    try:

        # ----------------------------------------------------
        # Load source
        # ----------------------------------------------------

        print()
        print(
            "Loading Sun_Moon_Position..."
        )

        source_rows = load_source_rows(
            connection
        )

        print(
            f"Source rows: {len(source_rows):,}"
        )

        if not source_rows:
            raise RuntimeError(
                "No Sun_Moon_Position rows found."
            )

        # ----------------------------------------------------
        # Find exact 6° boundaries
        # ----------------------------------------------------

        print()
        print(
            "Finding exact 6° Karana boundaries..."
        )

        boundaries = find_boundaries(
            source_rows
        )

        print(
            f"Exact boundaries found: "
            f"{len(boundaries):,}"
        )

        # ----------------------------------------------------
        # Build intervals
        # ----------------------------------------------------

        print()
        print(
            "Building Karana intervals..."
        )

        intervals = build_karana_intervals(
            boundaries
        )

        print(
            f"Karana intervals: "
            f"{len(intervals):,}"
        )

        # ----------------------------------------------------
        # Write database
        # ----------------------------------------------------

        print()
        print(
            "Writing Karana_Transition..."
        )

        write_database(
            connection,
            intervals,
        )

        print(
            "Database population complete."
        )

        # ----------------------------------------------------
        # Validation
        # ----------------------------------------------------

        validate(
            connection
        )

        # ----------------------------------------------------
        # Display first few rows
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("FIRST 10 KARANA TRANSITIONS")
        print("=" * 70)

        cursor = connection.execute(
            """
            SELECT
                Start_Date_Time_UTC,
                End_Date_Time_UTC,
                Angular_Separation_Start,
                Angular_Separation_End,
                Karana_Number,
                Karana,
                Is_Bhadra
            FROM Karana_Transition
            WHERE Location = ?
            ORDER BY Start_Date_Time_UTC
            LIMIT 10
            """,
            (LOCATION,),
        )

        for row in cursor:
            print(
                "|".join(
                    str(value)
                    for value in row
                )
            )

    finally:
        connection.close()


if __name__ == "__main__":
    main()
