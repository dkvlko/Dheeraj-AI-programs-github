#!/usr/bin/env python3

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import swisseph as swe


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"
LATITUDE = 26.8467
LONGITUDE = 80.9462
TIMEZONE = ZoneInfo("Asia/Kolkata")

# Rebuild period.
#
# Set these to the range covered by Sun_Moon_Position.
START_YEAR = 1926
END_YEAR = 2126

# Swiss Ephemeris
EPHEMERIS_FLAGS = swe.FLG_SWIEPH


# ============================================================
# DATABASE
# ============================================================

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# DATETIME FUNCTIONS
# ============================================================

def parse_datetime(value: str) -> datetime:
    """
    Parse ISO datetime and return timezone-aware datetime.
    """
    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        raise ValueError(f"Datetime has no timezone: {value}")

    return dt


def format_utc(dt: datetime) -> str:
    """
    Format datetime as UTC ISO string.
    """
    dt = dt.astimezone(timezone.utc)
    return dt.isoformat(timespec="microseconds")


def format_local(dt: datetime) -> str:
    """
    Format datetime in Asia/Kolkata.
    """
    dt = dt.astimezone(TIMEZONE)
    return dt.isoformat(timespec="microseconds")


# ============================================================
# ANGULAR FUNCTIONS
# ============================================================

def normalize_angle(angle: float) -> float:
    """
    Normalize angle to [0, 360).
    """
    return angle % 360.0


def angular_separation(sun_longitude: float,
                       moon_longitude: float) -> float:
    """
    Geocentric Moon-Sun angular separation.

    Result:
        0 <= separation < 360
    """
    return normalize_angle(moon_longitude - sun_longitude)


def unwrap_forward(start: float, end: float) -> float:
    """
    Convert an angular separation transition into a monotonically
    increasing value.

    Example:

        359 -> 2

    becomes:

        359 -> 362
    """

    end = normalize_angle(end)

    while end < start:
        end += 360.0

    return end


# ============================================================
# SWISS EPHEMERIS
# ============================================================

def datetime_to_julian_day(dt: datetime) -> float:
    """
    Convert timezone-aware UTC datetime to Julian Day UT.
    """

    dt_utc = dt.astimezone(timezone.utc)

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


def get_sun_moon_separation(dt: datetime) -> float:
    """
    Calculate geocentric Moon-Sun angular separation using
    Swiss Ephemeris.
    """

    jd = datetime_to_julian_day(dt)

    sun, _ = swe.calc_ut(
        jd,
        swe.SUN,
        EPHEMERIS_FLAGS,
    )

    moon, _ = swe.calc_ut(
        jd,
        swe.MOON,
        EPHEMERIS_FLAGS,
    )

    sun_longitude = normalize_angle(sun[0])
    moon_longitude = normalize_angle(moon[0])

    return angular_separation(
        sun_longitude,
        moon_longitude,
    )


# ============================================================
# ROOT FINDING
# ============================================================

def angular_distance_forward(value: float,
                             target: float) -> float:
    """
    Forward angular distance from value to target.

    Both values are normalized to [0, 360).
    """

    return (target - value) % 360.0


def find_crossing(
    start_dt: datetime,
    end_dt: datetime,
    start_angle: float,
    end_angle: float,
    target_angle: float,
) -> datetime:
    """
    Find the exact time at which angular separation crosses
    target_angle.

    The input interval is assumed to contain the crossing.

    Bisection is used. Swiss Ephemeris is evaluated directly
    at every midpoint.

    Accuracy:
        approximately better than one microsecond in the
        datetime interval, subject to datetime resolution and
        ephemeris numerical precision.
    """

    start_angle = normalize_angle(start_angle)
    end_angle = normalize_angle(end_angle)
    target_angle = normalize_angle(target_angle)

    # Determine the forward-unwrapped end angle.
    end_unwrapped = unwrap_forward(
        start_angle,
        end_angle,
    )

    # Target must be placed after start_angle on this
    # particular forward path.
    target_offset = angular_distance_forward(
        start_angle,
        target_angle,
    )

    target_unwrapped = start_angle + target_offset

    if not (
        start_angle <= target_unwrapped <= end_unwrapped
    ):
        raise RuntimeError(
            "Target angle is not inside bracket: "
            f"{start_angle} -> {end_angle}, "
            f"target={target_angle}"
        )

    total_seconds = (
        end_dt - start_dt
    ).total_seconds()

    # Bisection.
    lo_dt = start_dt
    hi_dt = end_dt

    lo_value = start_angle

    for _ in range(100):

        if (
            hi_dt - lo_dt
        ).total_seconds() <= 0.000001:
            break

        mid_dt = lo_dt + (
            hi_dt - lo_dt
        ) / 2

        mid_angle = get_sun_moon_separation(mid_dt)

        # Put midpoint on same unwrapped angular branch
        # as lo_angle.
        mid_unwrapped = mid_angle

        while mid_unwrapped < lo_value:
            mid_unwrapped += 360.0

        # It is possible for the midpoint to be numerically
        # just on the next branch.
        while mid_unwrapped > lo_value + 360.0:
            mid_unwrapped -= 360.0

        if mid_unwrapped < target_unwrapped:
            lo_dt = mid_dt
            lo_value = mid_unwrapped
        else:
            hi_dt = mid_dt

    return lo_dt + (
        hi_dt - lo_dt
    ) / 2


# ============================================================
# READ 3-HOUR SOURCE DATA
# ============================================================

def get_source_rows(conn: sqlite3.Connection):
    """
    Read the existing 3-hour Sun_Moon_Position observations.
    """

    start_date = f"{START_YEAR:04d}-01-01T00:00:00"
    end_date = f"{END_YEAR + 1:04d}-01-01T00:00:00"

    rows = conn.execute(
        """
        SELECT
            Date_Time_UTC,
            Date_Time_Local,
            Sun_Longitude,
            Moon_Longitude,
            Angular_Separation
        FROM Sun_Moon_Position
        WHERE Location = ?
          AND Date_Time_Local >= ?
          AND Date_Time_Local < ?
        ORDER BY Date_Time_UTC
        """,
        (
            LOCATION,
            start_date,
            end_date,
        ),
    ).fetchall()

    return rows


# ============================================================
# TRANSITION DETECTION
# ============================================================

def classify_crossings(
    start_angle: float,
    end_angle: float,
):
    """
    Return the phase boundaries crossed by this source interval.

    Possible boundaries:

        168° = beginning of Purnima
        180° = end of Purnima
        348° = beginning of Amavasya
        360° = end of Amavasya
                    (= 0°)
    """

    start_angle = normalize_angle(start_angle)
    end_angle = normalize_angle(end_angle)

    end_unwrapped = unwrap_forward(
        start_angle,
        end_angle,
    )

    crossings = []

    # Test the four relevant boundaries.
    #
    # We use several branches because a boundary may be
    # represented as 0°/360°.
    for target in (
        168.0,
        180.0,
        348.0,
        360.0,
    ):

        # Convert target to the branch immediately following
        # start_angle.
        target_offset = (
            target - start_angle
        ) % 360.0

        target_unwrapped = (
            start_angle + target_offset
        )

        if (
            start_angle
            < target_unwrapped
            <= end_unwrapped
        ):
            crossings.append(
                (
                    target,
                    target_unwrapped,
                )
            )

    return crossings


# ============================================================
# BUILD EXACT PURNIMA / AMAVASYA INTERVALS
# ============================================================

def build_intervals(rows):
    """
    Find exact 168° and 180° crossings from the 3-hour
    source observations.

    Returns:

        [
            {
                "phase": "Purnima",
                "start": datetime,
                "end": datetime,
                ...
            },
            ...
        ]
    """

    exact_crossings = []

    for i in range(len(rows) - 1):

        row1 = rows[i]
        row2 = rows[i + 1]

        dt1 = parse_datetime(
            row1["Date_Time_UTC"]
        )

        dt2 = parse_datetime(
            row2["Date_Time_UTC"]
        )

        angle1 = normalize_angle(
            row1["Angular_Separation"]
        )

        angle2 = normalize_angle(
            row2["Angular_Separation"]
        )

        crossings = classify_crossings(
            angle1,
            angle2,
        )

        for target_angle, _ in crossings:

            crossing_dt = find_crossing(
                dt1,
                dt2,
                angle1,
                angle2,
                target_angle,
            )

            exact_crossings.append(
                (
                    crossing_dt,
                    target_angle,
                )
            )

    # Sort and remove duplicates.
    exact_crossings.sort(
        key=lambda x: x[0]
    )

    unique_crossings = []

    for dt, angle in exact_crossings:

        if not unique_crossings:
            unique_crossings.append(
                (dt, angle)
            )
            continue

        previous_dt, previous_angle = (
            unique_crossings[-1]
        )

        if (
            abs(
                (
                    dt - previous_dt
                ).total_seconds()
            ) < 1.0
            and abs(angle - previous_angle) < 0.001
        ):
            continue

        unique_crossings.append(
            (dt, angle)
        )

    # --------------------------------------------------------
    # Convert crossings into intervals.
    #
    # Purnima:
    #       168 -> 180
    #
    # Amavasya:
    #       348 -> 360
    # --------------------------------------------------------

    intervals = []

    for i in range(len(unique_crossings) - 1):

        start_dt, start_angle = (
            unique_crossings[i]
        )

        end_dt, end_angle = (
            unique_crossings[i + 1]
        )

        if (
            abs(start_angle - 168.0) < 0.001
            and abs(end_angle - 180.0) < 0.001
        ):

            intervals.append(
                {
                    "phase": "Purnima",
                    "start": start_dt,
                    "end": end_dt,
                    "start_angle": 168.0,
                    "end_angle": 180.0,
                }
            )

        elif (
            abs(start_angle - 348.0) < 0.001
            and (
                abs(end_angle - 360.0) < 0.001
                or abs(end_angle) < 0.001
            )
        ):

            intervals.append(
                {
                    "phase": "Amavasya",
                    "start": start_dt,
                    "end": end_dt,
                    "start_angle": 348.0,
                    "end_angle": 360.0,
                }
            )

    return intervals


# ============================================================
# CREATE TABLE
# ============================================================

def recreate_transition_table(
    conn: sqlite3.Connection,
):
    """
    Recreate Amavasya_Purnima_Transition.
    """

    conn.execute(
        """
        DROP TABLE IF EXISTS Amavasya_Purnima_Transition
        """
    )

    conn.execute(
        """
        CREATE TABLE Amavasya_Purnima_Transition (
            Start_Date_Time_UTC TEXT NOT NULL,
            End_Date_Time_UTC TEXT NOT NULL,

            Start_Date_Time_Local TEXT NOT NULL,
            End_Date_Time_Local TEXT NOT NULL,

            Location TEXT NOT NULL,
            Latitude REAL NOT NULL,
            Longitude REAL NOT NULL,

            Phase TEXT NOT NULL,

            Angular_Separation_Start REAL NOT NULL,
            Angular_Separation_End REAL NOT NULL,

            PRIMARY KEY (
                Start_Date_Time_UTC,
                Location
            )
        )
        """
    )

    conn.commit()


# ============================================================
# INSERT INTERVALS
# ============================================================

def insert_intervals(
    conn: sqlite3.Connection,
    intervals,
):

    for interval in intervals:

        start_dt = interval["start"]
        end_dt = interval["end"]

        conn.execute(
            """
            INSERT INTO Amavasya_Purnima_Transition (
                Start_Date_Time_UTC,
                End_Date_Time_UTC,

                Start_Date_Time_Local,
                End_Date_Time_Local,

                Location,
                Latitude,
                Longitude,

                Phase,

                Angular_Separation_Start,
                Angular_Separation_End
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                format_utc(start_dt),
                format_utc(end_dt),

                format_local(start_dt),
                format_local(end_dt),

                LOCATION,
                LATITUDE,
                LONGITUDE,

                interval["phase"],

                interval["start_angle"],
                interval["end_angle"],
            ),
        )

    conn.commit()


# ============================================================
# STATISTICS
# ============================================================

def print_statistics(
    conn: sqlite3.Connection,
):

    total = conn.execute(
        """
        SELECT COUNT(*)
        FROM Amavasya_Purnima_Transition
        """
    ).fetchone()[0]

    purnima = conn.execute(
        """
        SELECT COUNT(*)
        FROM Amavasya_Purnima_Transition
        WHERE Phase = 'Purnima'
        """
    ).fetchone()[0]

    amavasya = conn.execute(
        """
        SELECT COUNT(*)
        FROM Amavasya_Purnima_Transition
        WHERE Phase = 'Amavasya'
        """
    ).fetchone()[0]

    print()
    print("=" * 70)
    print("Amavasya_Purnima_Transition")
    print("=" * 70)

    print(
        f"Total intervals : {total:,}"
    )

    print(
        f"Purnima         : {purnima:,}"
    )

    print(
        f"Amavasya        : {amavasya:,}"
    )

    print("=" * 70)


# ============================================================
# SAMPLE OUTPUT
# ============================================================

def print_sample(
    conn: sqlite3.Connection,
    year: int,
):

    rows = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Phase,
            Angular_Separation_Start,
            Angular_Separation_End
        FROM Amavasya_Purnima_Transition
        WHERE Location = ?
          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local < ?
        ORDER BY Start_Date_Time_Local
        """,
        (
            LOCATION,
            f"{year:04d}-01-01",
            f"{year + 1:04d}-01-01",
        ),
    ).fetchall()

    print()
    print("=" * 70)
    print(f"TRANSITIONS FOR {year}")
    print("=" * 70)

    for row in rows:

        print(
            f"{row['Start_Date_Time_Local']}"
            f"  ->  "
            f"{row['End_Date_Time_Local']}"
            f"  | "
            f"{row['Phase']}"
            f"  | "
            f"{row['Angular_Separation_Start']:.1f}"
            f" -> "
            f"{row['Angular_Separation_End']:.1f}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("REBUILDING Amavasya_Purnima_Transition")
    print("=" * 70)

    print(
        f"Database : {DB_PATH}"
    )

    print(
        f"Location : {LOCATION}"
    )

    print(
        f"Period   : {START_YEAR} - {END_YEAR}"
    )

    conn = get_connection()

    try:

        # ----------------------------------------------------
        # Read existing 3-hour observations.
        # ----------------------------------------------------

        rows = get_source_rows(conn)

        print()
        print(
            f"Sun_Moon_Position rows read: {len(rows):,}"
        )

        if len(rows) < 2:
            raise RuntimeError(
                "Not enough Sun_Moon_Position rows."
            )

        # ----------------------------------------------------
        # Build exact intervals.
        # ----------------------------------------------------

        print()
        print(
            "Finding exact 168° / 180° / "
            "348° / 360° transitions..."
        )

        intervals = build_intervals(rows)

        print(
            f"Intervals found: {len(intervals):,}"
        )

        # ----------------------------------------------------
        # Recreate destination table.
        # ----------------------------------------------------

        print()
        print(
            "Recreating Amavasya_Purnima_Transition..."
        )

        recreate_transition_table(conn)

        # ----------------------------------------------------
        # Insert.
        # ----------------------------------------------------

        print(
            "Inserting intervals..."
        )

        insert_intervals(
            conn,
            intervals,
        )

        # ----------------------------------------------------
        # Statistics.
        # ----------------------------------------------------

        print_statistics(conn)

        # ----------------------------------------------------
        # Show 2026 and 2027.
        # ----------------------------------------------------

        print_sample(conn, 2026)
        print_sample(conn, 2027)

        print()
        print(
            "Rebuild completed successfully."
        )

    finally:

        conn.close()


if __name__ == "__main__":
    main()
