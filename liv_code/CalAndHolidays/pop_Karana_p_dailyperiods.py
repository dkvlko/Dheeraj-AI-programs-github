#!/usr/bin/env python3

"""
Populate:

    1. Karana_Transition
    2. Daily_Time_Periods

Database:
    /data/BLOBS/CalAndHolidays/CalAndHolidays.db

Location:
    Lucknow, Uttar Pradesh, India

Calendar:
    Amanta

Important:
    - Karana boundaries are defined at every 6 degrees of
      Moon-Sun angular separation.
    - We retain the exact 6-degree definition.
    - Transition TIMES are approximated using linear interpolation
      between 12-hour Swiss Ephemeris samples.
    - This is intentionally faster than binary-searching every
      transition.

Expected accuracy:
    Usually within a few minutes for transition times, which is
    more than adequate for the intended festival-rule database.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe


# ================================================================
# CONFIGURATION
# ================================================================

DATABASE_PATH = Path(
    "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"
)

LOCATION = "Lucknow, Uttar Pradesh, India"

LATITUDE = 26.8467
LONGITUDE = 80.9462

TIMEZONE = ZoneInfo("Asia/Kolkata")

CALENDAR_SYSTEM = "Amanta"

# ------------------------------------------------
# Requested output range
# ------------------------------------------------

START_DATE = date(1926, 1, 1)
END_DATE = date(2126, 12, 31)

# Add a little margin so transitions at the boundaries
# are safely captured.
CALC_START_DATE = START_DATE - timedelta(days=2)
CALC_END_DATE = END_DATE + timedelta(days=2)

# ------------------------------------------------
# Fast scan resolution
# ------------------------------------------------

SCAN_STEP = timedelta(hours=12)

# ------------------------------------------------
# Pradosh convention used by this database
# ------------------------------------------------

PRADOSH_DURATION = timedelta(minutes=144)

# ------------------------------------------------
# Commit frequency
# ------------------------------------------------

COMMIT_EVERY = 100


# ================================================================
# SWISS EPHEMERIS
# ================================================================

swe.set_sid_mode(swe.SIDM_LAHIRI)

FLAGS = (
    swe.FLG_SWIEPH
    | swe.FLG_SPEED
    | swe.FLG_SIDEREAL
)


# ================================================================
# KARANA DEFINITIONS
# ================================================================

MOVABLE_KARANAS = [
    "Bava",
    "Balava",
    "Kaulava",
    "Taitila",
    "Gara",
    "Vanija",
    "Vishti",
]

FIXED_KARANAS = {
    1: "Kimstughna",
    57: "Shakuni",
    58: "Chatushpada",
    59: "Naga",
    60: "Kimstughna",
}


def karana_from_position(position: int) -> str:
    """
    Convert Karana position 1..60 to its name.

    Positions:
        1       Kimstughna
        2..56   repeating movable Karanas
        57      Shakuni
        58      Chatushpada
        59      Naga
        60      Kimstughna
    """

    if position in FIXED_KARANAS:
        return FIXED_KARANAS[position]

    # Positions 2..56
    index = (position - 2) % 7

    return MOVABLE_KARANAS[index]


def karana_position_from_separation(separation: float) -> int:
    """
    Convert Moon-Sun angular separation into Karana position.

    Every Karana spans exactly 6 degrees.

        0-6       -> position 1
        6-12      -> position 2
        ...
        354-360   -> position 60
    """

    # Protect against floating-point 360.0
    separation %= 360.0

    position = int(separation // 6.0) + 1

    if position > 60:
        position = 60

    return position


def is_bhadra(karana: str) -> int:
    """
    Bhadra = Vishti Karana.
    """

    return 1 if karana == "Vishti" else 0


# ================================================================
# JULIAN DAY
# ================================================================

def datetime_to_jd(dt_utc: datetime) -> float:
    """
    Convert timezone-aware UTC datetime to Julian Day.
    """

    dt_utc = dt_utc.astimezone(ZoneInfo("UTC"))

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


def jd_to_datetime_utc(jd: float) -> datetime:
    """
    Convert Julian Day to timezone-aware UTC datetime.
    """

    year, month, day, hour = swe.revjul(
        jd,
        swe.GREG_CAL,
    )

    hour_int = int(hour)

    minute_float = (hour - hour_int) * 60.0
    minute_int = int(minute_float)

    second_float = (minute_float - minute_int) * 60.0
    second_int = int(second_float)

    microsecond = int(
        round((second_float - second_int) * 1_000_000)
    )

    # Handle rounding overflow.
    if microsecond >= 1_000_000:
        second_int += 1
        microsecond -= 1_000_000

    dt = datetime(
        int(year),
        int(month),
        int(day),
        hour_int,
        minute_int,
        second_int,
        microsecond,
        tzinfo=ZoneInfo("UTC"),
    )

    return dt


# ================================================================
# ASTRONOMICAL CALCULATION
# ================================================================

def get_angular_separation(dt_utc: datetime) -> float:
    """
    Return sidereal Moon-Sun angular separation in degrees.
    """

    jd = datetime_to_jd(dt_utc)

    sun_result = swe.calc_ut(
        jd,
        swe.SUN,
        FLAGS,
    )

    moon_result = swe.calc_ut(
        jd,
        swe.MOON,
        FLAGS,
    )

    sun_longitude = sun_result[0][0]
    moon_longitude = moon_result[0][0]

    separation = (
        moon_longitude
        - sun_longitude
    ) % 360.0

    return separation


# ================================================================
# UNWRAP ANGULAR MOVEMENT
# ================================================================

def forward_angular_difference(
    start: float,
    end: float,
) -> float:
    """
    Return forward angular movement from start to end.

    Example:

        358 -> 2

    gives:

        4 degrees

    rather than -356 degrees.
    """

    return (end - start) % 360.0


# ================================================================
# FIND APPROXIMATE CROSSING
# ================================================================

def interpolate_crossing_time(
    t1: datetime,
    sep1: float,
    t2: datetime,
    sep2: float,
    boundary: float,
) -> datetime:
    """
    Approximate the time at which angular separation crossed
    a particular 6-degree boundary.

    Uses linear interpolation.

    This deliberately avoids iterative Swiss Ephemeris
    root-finding for speed.
    """

    movement = forward_angular_difference(
        sep1,
        sep2,
    )

    if movement <= 0.0:
        return t1

    distance = forward_angular_difference(
        sep1,
        boundary,
    )

    fraction = distance / movement

    # Numerical protection.
    fraction = max(
        0.0,
        min(1.0, fraction),
    )

    elapsed = t2 - t1

    return t1 + elapsed * fraction


# ================================================================
# GENERATE KARANA TRANSITIONS
# ================================================================

def populate_karana_transition(
    connection: sqlite3.Connection,
) -> None:

    print()
    print("Generating Karana_Transition")
    print("=" * 70)

    cursor = connection.cursor()

    # ------------------------------------------------------------
    # Clear existing generated data.
    # ------------------------------------------------------------

    cursor.execute(
        """
        DELETE FROM Karana_Transition
        WHERE Location = ?
        """,
        (LOCATION,),
    )

    connection.commit()

    # ------------------------------------------------------------
    # Initial timestamp.
    # ------------------------------------------------------------

    current = datetime(
        CALC_START_DATE.year,
        CALC_START_DATE.month,
        CALC_START_DATE.day,
        0,
        0,
        0,
        tzinfo=ZoneInfo("UTC"),
    )

    end = datetime(
        CALC_END_DATE.year,
        CALC_END_DATE.month,
        CALC_END_DATE.day,
        23,
        59,
        59,
        tzinfo=ZoneInfo("UTC"),
    )

    # ------------------------------------------------------------
    # First astronomical value.
    # ------------------------------------------------------------

    sep1 = get_angular_separation(current)

    rows_inserted = 0

    # ------------------------------------------------------------
    # Scan 12 hours at a time.
    # ------------------------------------------------------------

    while current < end:

        next_time = min(
            current + SCAN_STEP,
            end,
        )

        sep2 = get_angular_separation(next_time)

        movement = forward_angular_difference(
            sep1,
            sep2,
        )

        # --------------------------------------------------------
        # Determine every 6-degree boundary crossed.
        #
        # This is the important part that fixes the previous
        # "change=6.080175" error.
        # --------------------------------------------------------

        start_position = (
            int(sep1 // 6.0)
        )

        boundaries = []

        boundary_index = start_position + 1

        accumulated = 0.0

        while accumulated < movement:

            boundary = (
                boundary_index * 6.0
            ) % 360.0

            distance = forward_angular_difference(
                sep1,
                boundary,
            )

            if distance <= movement + 1e-12:

                boundaries.append(
                    (
                        boundary,
                        distance,
                    )
                )

            boundary_index += 1

            accumulated = (
                boundary_index * 6.0
                - start_position * 6.0
            )

            if boundary_index > start_position + 61:
                break

        # --------------------------------------------------------
        # If no boundary was crossed, continue.
        # --------------------------------------------------------

        if not boundaries:

            current = next_time
            sep1 = sep2
            continue

        # --------------------------------------------------------
        # Process each crossed boundary.
        # --------------------------------------------------------

        previous_transition_time = None

        for boundary, distance in boundaries:

            transition_time = (
                interpolate_crossing_time(
                    current,
                    sep1,
                    next_time,
                    sep2,
                    boundary,
                )
            )

            # ----------------------------------------------------
            # Determine the Karana AFTER crossing the boundary.
            # ----------------------------------------------------

            new_position = (
                int(boundary // 6.0) + 1
            )

            if new_position > 60:
                new_position = 60

            new_karana = karana_from_position(
                new_position
            )

            # ----------------------------------------------------
            # The interval BEFORE this transition belongs to the
            # previous Karana.
            #
            # We therefore need the previous transition time.
            #
            # For the first transition in this scan interval,
            # we don't necessarily have the true previous
            # transition in memory. We obtain it from the
            # current Karana start logic below.
            # ----------------------------------------------------

            if previous_transition_time is None:

                # Find the current Karana start by interpolating
                # backwards to the previous 6-degree boundary.

                previous_boundary = (
                    (int(sep1 // 6.0)) * 6.0
                ) % 360.0

                distance_back = (
                    forward_angular_difference(
                        previous_boundary,
                        sep1,
                    )
                )

                movement_total = (
                    forward_angular_difference(
                        sep1,
                        sep2,
                    )
                )

                # If sep1 itself is essentially on a boundary,
                # use current as the approximate start.
                if distance_back < 1e-10:

                    interval_start = current

                else:

                    # Estimate how far before current the
                    # previous boundary occurred.
                    #
                    # Since we don't know the exact historical
                    # speed, use the local scan rate.
                    #
                    # This branch is mainly for the first
                    # interval and is replaced by actual
                    # transitions for subsequent intervals.

                    if movement_total > 0:

                        fraction = (
                            distance_back
                            / movement_total
                        )

                        interval_start = (
                            current
                            - (next_time - current)
                            * fraction
                        )

                    else:

                        interval_start = current

            else:

                interval_start = previous_transition_time

            # ----------------------------------------------------
            # We need to store the Karana that existed BEFORE
            # this boundary.
            # ----------------------------------------------------

            before_position = (
                new_position - 1
            )

            if before_position < 1:
                before_position = 60

            before_karana = karana_from_position(
                before_position
            )

            # ----------------------------------------------------
            # Do not create zero/negative intervals.
            # ----------------------------------------------------

            if transition_time > interval_start:

                start_utc = interval_start
                end_utc = transition_time

                start_local = (
                    start_utc
                    .astimezone(TIMEZONE)
                )

                end_local = (
                    end_utc
                    .astimezone(TIMEZONE)
                )

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO Karana_Transition (
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        start_utc.isoformat(),
                        end_utc.isoformat(),
                        start_local.isoformat(),
                        end_local.isoformat(),
                        LOCATION,
                        sep1,
                        boundary,
                        f"{before_position:02d}",
                        before_karana,
                        is_bhadra(before_karana),
                    ),
                )

                rows_inserted += 1

                if rows_inserted % COMMIT_EVERY == 0:

                    connection.commit()

                    print(
                        f"  inserted {rows_inserted:,} intervals "
                        f"... {transition_time.date()}"
                    )

            previous_transition_time = transition_time

        # --------------------------------------------------------
        # Continue scanning.
        # --------------------------------------------------------

        current = next_time
        sep1 = sep2

    connection.commit()

    print()
    print(
        f"Karana_Transition complete: "
        f"{rows_inserted:,} rows"
    )


# ================================================================
# REBUILD KARANA INTERVAL END TIMES
# ================================================================

def rebuild_karana_intervals(
    connection: sqlite3.Connection,
) -> None:
    """
    The fast scanner above generates approximate transition
    boundaries. This function reconstructs the intervals from
    consecutive transition records.

    This gives the database a clean sequence:

        transition N
            ->
        transition N+1

    without requiring expensive astronomical calculations.
    """

    print()
    print("Rebuilding Karana interval boundaries")
    print("=" * 70)

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            Start_Date_Time_UTC,
            Karana_Number,
            Karana,
            Is_Bhadra
        FROM Karana_Transition
        WHERE Location = ?
        ORDER BY Start_Date_Time_UTC
        """,
        (LOCATION,),
    )

    rows = cursor.fetchall()

    if not rows:
        print("No Karana rows found.")
        return

    # ------------------------------------------------------------
    # Rebuild every interval using the next transition.
    # ------------------------------------------------------------

    updates = []

    for i in range(len(rows) - 1):

        start_utc = datetime.fromisoformat(
            rows[i][0]
        )

        end_utc = datetime.fromisoformat(
            rows[i + 1][0]
        )

        start_local = (
            start_utc.astimezone(TIMEZONE)
        )

        end_local = (
            end_utc.astimezone(TIMEZONE)
        )

        updates.append(
            (
                end_utc.isoformat(),
                end_local.isoformat(),
                start_local.isoformat(),
                rows[i][0],
            )
        )

    # ------------------------------------------------------------
    # Update End_Date_Time.
    # ------------------------------------------------------------

    cursor.executemany(
        """
        UPDATE Karana_Transition
        SET
            End_Date_Time_UTC = ?,
            End_Date_Time_Local = ?,
            Start_Date_Time_Local = ?
        WHERE Start_Date_Time_UTC = ?
          AND Location = ?
        """,
        [
            (
                end_utc,
                end_local,
                start_local,
                start_utc,
                LOCATION,
            )
            for (
                end_utc,
                end_local,
                start_local,
                start_utc,
            ) in updates
        ],
    )

    connection.commit()

    print(
        f"Rebuilt {len(updates):,} Karana intervals."
    )


# ================================================================
# DAILY TIME PERIODS
# ================================================================

def populate_daily_time_periods(
    connection: sqlite3.Connection,
) -> None:

    print()
    print("Generating Daily_Time_Periods")
    print("=" * 70)

    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM Daily_Time_Periods
        WHERE Location = ?
        """,
        (LOCATION,),
    )

    connection.commit()

    cursor.execute(
        """
        SELECT
            Date,
            Sunrise_Time,
            Sunset_Time
        FROM Sun_Position
        WHERE Location = ?
          AND Date BETWEEN ? AND ?
        ORDER BY Date
        """,
        (
            LOCATION,
            START_DATE.isoformat(),
            END_DATE.isoformat(),
        ),
    )

    rows = cursor.fetchall()

    inserted = 0

    for row in rows:

        date_text = row[0]
        sunrise_text = row[1]
        sunset_text = row[2]

        # --------------------------------------------------------
        # Construct local datetime values.
        # --------------------------------------------------------

        sunrise_dt = datetime.fromisoformat(
            f"{date_text}T{sunrise_text}"
        ).replace(
            tzinfo=TIMEZONE
        )

        sunset_dt = datetime.fromisoformat(
            f"{date_text}T{sunset_text}"
        ).replace(
            tzinfo=TIMEZONE
        )

        # --------------------------------------------------------
        # Recommended Pradosh convention:
        #
        # sunset -> sunset + 144 minutes
        # --------------------------------------------------------

        pradosh_start = sunset_dt

        pradosh_end = (
            sunset_dt
            + PRADOSH_DURATION
        )

        cursor.execute(
            """
            INSERT OR REPLACE INTO Daily_Time_Periods (
                Date,
                Location,
                Sunrise_Time,
                Sunset_Time,
                Pradosh_Start,
                Pradosh_End
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                date_text,
                LOCATION,
                sunrise_dt.time().isoformat(),
                sunset_dt.time().isoformat(),
                pradosh_start.isoformat(),
                pradosh_end.isoformat(),
            ),
        )

        inserted += 1

        if inserted % COMMIT_EVERY == 0:

            connection.commit()

            print(
                f"  inserted {inserted:,} days ..."
            )

    connection.commit()

    print()
    print(
        f"Daily_Time_Periods complete: "
        f"{inserted:,} rows"
    )


# ================================================================
# BASIC VALIDATION
# ================================================================

def validate_database(
    connection: sqlite3.Connection,
) -> None:

    print()
    print("Validation")
    print("=" * 70)

    cursor = connection.cursor()

    # ------------------------------------------------------------
    # Karana count
    # ------------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM Karana_Transition
        WHERE Location = ?
        """,
        (LOCATION,),
    )

    karana_count = cursor.fetchone()[0]

    print(
        f"Karana_Transition rows : {karana_count:,}"
    )

    # ------------------------------------------------------------
    # Bhadra count
    # ------------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM Karana_Transition
        WHERE Location = ?
          AND Is_Bhadra = 1
        """,
        (LOCATION,),
    )

    bhadra_count = cursor.fetchone()[0]

    print(
        f"Bhadra intervals       : {bhadra_count:,}"
    )

    # ------------------------------------------------------------
    # Daily periods
    # ------------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM Daily_Time_Periods
        WHERE Location = ?
        """,
        (LOCATION,),
    )

    daily_count = cursor.fetchone()[0]

    print(
        f"Daily_Time_Periods     : {daily_count:,}"
    )

    # ------------------------------------------------------------
    # Show first few Karana records
    # ------------------------------------------------------------

    print()
    print("First 5 Karana records:")

    cursor.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Karana_Number,
            Karana,
            Is_Bhadra
        FROM Karana_Transition
        WHERE Location = ?
        ORDER BY Start_Date_Time_UTC
        LIMIT 5
        """,
        (LOCATION,),
    )

    for row in cursor.fetchall():

        print(
            "  ",
            row
        )

    # ------------------------------------------------------------
    # Show first few Bhadra records
    # ------------------------------------------------------------

    print()
    print("First 5 Bhadra records:")

    cursor.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Karana_Number,
            Karana
        FROM Karana_Transition
        WHERE Location = ?
          AND Is_Bhadra = 1
        ORDER BY Start_Date_Time_UTC
        LIMIT 5
        """,
        (LOCATION,),
    )

    for row in cursor.fetchall():

        print(
            "  ",
            row
        )


# ================================================================
# MAIN
# ================================================================

def main():

    print()
    print("=" * 70)
    print("CalAndHolidays - Fast Karana / Daily Period Generator")
    print("=" * 70)

    print()
    print(f"Database : {DATABASE_PATH}")
    print(f"Location : {LOCATION}")
    print(f"Range    : {START_DATE} -> {END_DATE}")
    print(f"Scan     : {SCAN_STEP}")
    print(f"Pradosh  : sunset -> sunset + {PRADOSH_DURATION}")

    # ------------------------------------------------------------
    # Connect
    # ------------------------------------------------------------

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    try:

        # --------------------------------------------------------
        # Generate Karana transitions.
        # --------------------------------------------------------

        populate_karana_transition(
            connection
        )

        # --------------------------------------------------------
        # Reconstruct interval endings.
        # --------------------------------------------------------

        rebuild_karana_intervals(
            connection
        )

        # --------------------------------------------------------
        # Generate daily periods.
        # --------------------------------------------------------

        populate_daily_time_periods(
            connection
        )

        # --------------------------------------------------------
        # Validate.
        # --------------------------------------------------------

        validate_database(
            connection
        )

    finally:

        connection.close()

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)


if __name__ == "__main__":
    main()
