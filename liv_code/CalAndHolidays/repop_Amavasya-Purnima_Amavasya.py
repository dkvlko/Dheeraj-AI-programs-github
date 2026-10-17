from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import swisseph as swe
from sqlalchemy import create_engine, text


# ============================================================
# CONFIGURATION
# ============================================================

DATABASE_URL = (
    "sqlite:////data/BLOBS/CalAndHolidays/"
    "CalAndHolidays.db"
)

LOCATION = "Lucknow, Uttar Pradesh, India"

LATITUDE = 26.8467
LONGITUDE = 80.9462

TIMEZONE = ZoneInfo("Asia/Kolkata")


# ============================================================
# SWISS EPHEMERIS
# ============================================================

swe.set_sid_mode(
    swe.SIDM_LAHIRI
)

FLAGS = (
    swe.FLG_SWIEPH
    | swe.FLG_SIDEREAL
)


# ============================================================
# DATABASE
# ============================================================

engine = create_engine(
    DATABASE_URL,
    future=True,
)


# ============================================================
# JULIAN DAY CONVERSION
# ============================================================

def datetime_to_jd(
    dt_utc: datetime,
) -> float:

    dt_utc = dt_utc.astimezone(
        timezone.utc
    )

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


# ============================================================
# PRECISE SUN/MOON LONGITUDES
# ============================================================

def get_sun_moon_longitudes(
    dt_utc: datetime,
) -> tuple[float, float]:

    jd_ut = datetime_to_jd(
        dt_utc
    )

    sun_position, _ = swe.calc_ut(
        jd_ut,
        swe.SUN,
        FLAGS,
    )

    moon_position, _ = swe.calc_ut(
        jd_ut,
        swe.MOON,
        FLAGS,
    )

    sun_longitude = (
        sun_position[0] % 360.0
    )

    moon_longitude = (
        moon_position[0] % 360.0
    )

    return (
        sun_longitude,
        moon_longitude,
    )


# ============================================================
# ANGULAR SEPARATION
# ============================================================

def calculate_angular_separation(
    sun_longitude: float,
    moon_longitude: float,
) -> float:

    return (
        moon_longitude
        - sun_longitude
    ) % 360.0


# ============================================================
# SIGNED CIRCULAR DIFFERENCE
# ============================================================

def circular_difference(
    angle: float,
    target: float,
) -> float:

    return (
        angle
        - target
        + 180.0
    ) % 360.0 - 180.0


# ============================================================
# EXACT ANGULAR SEPARATION AT A TIME
# ============================================================

def get_angular_separation(
    dt_utc: datetime,
) -> float:

    sun_longitude, moon_longitude = (
        get_sun_moon_longitudes(
            dt_utc
        )
    )

    return calculate_angular_separation(
        sun_longitude,
        moon_longitude,
    )


# ============================================================
# PRECISE ROOT SOLVER
# ============================================================

def solve_crossing(
    start_utc: datetime,
    end_utc: datetime,
    target: float,
    tolerance_seconds: float = 0.001,
) -> datetime:
    """
    Find the exact instant when:

        Moon longitude - Sun longitude = target

    target:
        0°   -> Amavasya
        180° -> Purnima

    Bisection is deliberately used instead of interpolation.
    """

    start_utc = start_utc.astimezone(
        timezone.utc
    )

    end_utc = end_utc.astimezone(
        timezone.utc
    )

    start_angle = get_angular_separation(
        start_utc
    )

    end_angle = get_angular_separation(
        end_utc
    )

    f_start = circular_difference(
        start_angle,
        target,
    )

    f_end = circular_difference(
        end_angle,
        target,
    )

    # Exact endpoint
    if abs(f_start) < 1e-12:
        return start_utc

    if abs(f_end) < 1e-12:
        return end_utc

    # The bracket must contain the root.
    if f_start * f_end > 0:

        raise RuntimeError(
            "\n"
            "Root not bracketed.\n"
            f"Start UTC : {start_utc.isoformat()}\n"
            f"End UTC   : {end_utc.isoformat()}\n"
            f"Start sep : {start_angle}\n"
            f"End sep   : {end_angle}\n"
            f"Target     : {target}\n"
            f"f_start   : {f_start}\n"
            f"f_end     : {f_end}\n"
        )

    # --------------------------------------------------------
    # BISECTION
    # --------------------------------------------------------

    while True:

        duration = (
            end_utc - start_utc
        ).total_seconds()

        if duration <= tolerance_seconds:

            return (
                start_utc
                + (
                    end_utc - start_utc
                ) / 2
            )

        midpoint = (
            start_utc
            + (
                end_utc - start_utc
            ) / 2
        )

        midpoint_angle = (
            get_angular_separation(
                midpoint
            )
        )

        f_mid = circular_difference(
            midpoint_angle,
            target,
        )

        if abs(f_mid) < 1e-12:
            return midpoint

        if f_start * f_mid <= 0:

            end_utc = midpoint
            f_end = f_mid

        else:

            start_utc = midpoint
            f_start = f_mid


# ============================================================
# CLASSIFY EVENT
# ============================================================

def phase_from_target(
    target: float,
) -> str:

    if abs(target - 180.0) < 1e-9:
        return "Purnima"

    if abs(target) < 1e-9:
        return "Amavasya"

    raise ValueError(
        f"Unknown phase target: {target}"
    )


# ============================================================
# LOAD EXISTING SUN_MOON_POSITION
# ============================================================

print()
print("=" * 70)
print("Loading Sun_Moon_Position")
print("=" * 70)

with engine.connect() as connection:

    rows = connection.execute(
        text("""
            SELECT
                Date_Time_UTC,
                Date_Time_Local,
                Sun_Longitude,
                Moon_Longitude,
                Angular_Separation
            FROM Sun_Moon_Position
            WHERE Location = :location
            ORDER BY Date_Time_UTC
        """),
        {
            "location": LOCATION
        },
    ).mappings().all()


print(
    f"Loaded {len(rows):,} records."
)


# ============================================================
# CONVERT SOURCE DATA
# ============================================================

samples = []

for row in rows:

    dt_utc = datetime.fromisoformat(
        row["Date_Time_UTC"]
    ).astimezone(
        timezone.utc
    )

    samples.append(
        {
            "dt": dt_utc,

            # These values come directly from
            # Sun_Moon_Position.
            "sun":
                float(row["Sun_Longitude"]),

            "moon":
                float(row["Moon_Longitude"]),

            "separation":
                float(
                    row["Angular_Separation"]
                ),
        }
    )


# ============================================================
# FIND CANDIDATE CROSSINGS
# ============================================================

print()
print(
    "Searching for Amavasya/Purnima brackets..."
)

brackets = []


for previous, current in zip(
    samples,
    samples[1:],
):

    a0 = previous["separation"]
    a1 = current["separation"]

    # --------------------------------------------------------
    # Unwrap the angular separation across 360°.
    # --------------------------------------------------------

    a1_unwrapped = a1

    if a1_unwrapped < a0:
        a1_unwrapped += 360.0

    # --------------------------------------------------------
    # Purnima = 180°
    # --------------------------------------------------------

    if (
        a0 < 180.0
        <= a1_unwrapped
    ):

        brackets.append(
            {
                "start":
                    previous["dt"],

                "end":
                    current["dt"],

                "target":
                    180.0,

                "phase":
                    "Purnima",
            }
        )

    # --------------------------------------------------------
    # Amavasya = 360°/0°
    # --------------------------------------------------------

    if (
        a0 < 360.0
        <= a1_unwrapped
    ):

        brackets.append(
            {
                "start":
                    previous["dt"],

                "end":
                    current["dt"],

                "target":
                    0.0,

                "phase":
                    "Amavasya",
            }
        )


print(
    f"Found {len(brackets):,} candidate crossings."
)


# ============================================================
# SOLVE EVERY CROSSING PRECISELY
# ============================================================

print()
print(
    "Solving crossings with Swiss Ephemeris..."
)

events = []


for index, bracket in enumerate(
    brackets,
    start=1,
):

    event_time = solve_crossing(
        start_utc=bracket["start"],
        end_utc=bracket["end"],
        target=bracket["target"],
        tolerance_seconds=0.001,
    )

    (
        sun_longitude,
        moon_longitude,
    ) = get_sun_moon_longitudes(
        event_time
    )

    exact_separation = (
        calculate_angular_separation(
            sun_longitude,
            moon_longitude,
        )
    )

    events.append(
        {
            "dt_utc":
                event_time,

            "phase":
                bracket["phase"],

            "sun_longitude":
                sun_longitude,

            "moon_longitude":
                moon_longitude,

            "angular_separation":
                exact_separation,
        }
    )

    if index % 500 == 0:

        print(
            f"Solved "
            f"{index:,}/"
            f"{len(brackets):,}"
        )


# ============================================================
# SORT EVENTS
# ============================================================

events.sort(
    key=lambda row: row["dt_utc"]
)


# ============================================================
# REMOVE DUPLICATES
# ============================================================

unique_events = []

previous_time = None

for event in events:

    current_time = event["dt_utc"]

    if (
        previous_time is None
        or abs(
            (
                current_time
                - previous_time
            ).total_seconds()
        ) > 0.01
    ):

        unique_events.append(
            event
        )

        previous_time = current_time


events = unique_events


print()
print(
    f"Unique astronomical events: "
    f"{len(events):,}"
)


# ============================================================
# BUILD TRANSITION INTERVALS
# ============================================================

transitions = []


for current, following in zip(
    events,
    events[1:],
):

    start_utc = current["dt_utc"]
    end_utc = following["dt_utc"]

    # --------------------------------------------------------
    # The phase entered at the END of the interval.
    #
    # Therefore:
    #
    # Amavasya -> Purnima
    #       Phase = Purnima
    #
    # Purnima -> Amavasya
    #       Phase = Amavasya
    #
    # This makes the meaning of the Phase column explicit.
    # --------------------------------------------------------

    phase = following["phase"]

    transitions.append(
        {
            "start_utc":
                start_utc,

            "end_utc":
                end_utc,

            "start_local":
                start_utc.astimezone(
                    TIMEZONE
                ),

            "end_local":
                end_utc.astimezone(
                    TIMEZONE
                ),

            "phase":
                phase,

            "separation_start":
                current[
                    "angular_separation"
                ],

            "separation_end":
                following[
                    "angular_separation"
                ],
        }
    )


# ============================================================
# DATABASE REBUILD
# ============================================================

print()
print("=" * 70)
print("Rebuilding Amavasya/Purnima tables")
print("=" * 70)


with engine.begin() as connection:

    # --------------------------------------------------------
    # 1. Delete old event rows
    # --------------------------------------------------------

    print(
        "Deleting existing Amavasya_Purnima rows..."
    )

    connection.execute(
        text("""
            DELETE FROM Amavasya_Purnima
            WHERE Location = :location
        """),
        {
            "location": LOCATION
        },
    )

    # --------------------------------------------------------
    # 2. Delete old transition rows
    # --------------------------------------------------------

    print(
        "Deleting existing "
        "Amavasya_Purnima_Transition rows..."
    )

    connection.execute(
        text("""
            DELETE FROM Amavasya_Purnima_Transition
            WHERE Location = :location
        """),
        {
            "location": LOCATION
        },
    )

    # ========================================================
    # INSERT EXACT EVENTS
    # ========================================================

    print(
        "Inserting exact Amavasya/Purnima events..."
    )

    event_sql = text("""
        INSERT INTO Amavasya_Purnima (
            Date_Time_UTC,
            Date_Time_Local,
            Location,
            Latitude,
            Longitude,
            Sun_Longitude,
            Moon_Longitude,
            Angular_Separation,
            Tithi,
            Paksha,
            Lunar_Phase
        )
        VALUES (
            :date_time_utc,
            :date_time_local,
            :location,
            :latitude,
            :longitude,
            :sun_longitude,
            :moon_longitude,
            :angular_separation,
            :tithi,
            :paksha,
            :lunar_phase
        )
    """)


    event_rows = []

    for event in events:

        if event["phase"] == "Purnima":

            tithi = "15"
            paksha = "Shukla"

        else:

            tithi = "15"
            paksha = "Krishna"

        event_rows.append(
            {
                "date_time_utc":
                    event[
                        "dt_utc"
                    ].isoformat(),

                "date_time_local":
                    event[
                        "dt_utc"
                    ].astimezone(
                        TIMEZONE
                    ).isoformat(),

                "location":
                    LOCATION,

                "latitude":
                    LATITUDE,

                "longitude":
                    LONGITUDE,

                "sun_longitude":
                    event[
                        "sun_longitude"
                    ],

                "moon_longitude":
                    event[
                        "moon_longitude"
                    ],

                "angular_separation":
                    event[
                        "angular_separation"
                    ],

                "tithi":
                    tithi,

                "paksha":
                    paksha,

                "lunar_phase":
                    event["phase"],
            }
        )


    connection.execute(
        event_sql,
        event_rows,
    )


    # ========================================================
    # INSERT TRANSITIONS
    # ========================================================

    print(
        "Inserting exact phase transitions..."
    )

    transition_sql = text("""
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
        VALUES (
            :start_utc,
            :end_utc,
            :start_local,
            :end_local,
            :location,
            :latitude,
            :longitude,
            :phase,
            :separation_start,
            :separation_end
        )
    """)


    transition_rows = []

    for transition in transitions:

        transition_rows.append(
            {
                "start_utc":
                    transition[
                        "start_utc"
                    ].isoformat(),

                "end_utc":
                    transition[
                        "end_utc"
                    ].isoformat(),

                "start_local":
                    transition[
                        "start_local"
                    ].isoformat(),

                "end_local":
                    transition[
                        "end_local"
                    ].isoformat(),

                "location":
                    LOCATION,

                "latitude":
                    LATITUDE,

                "longitude":
                    LONGITUDE,

                "phase":
                    transition["phase"],

                "separation_start":
                    transition[
                        "separation_start"
                    ],

                "separation_end":
                    transition[
                        "separation_end"
                    ],
            }
        )


    connection.execute(
        transition_sql,
        transition_rows,
    )


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 70)
print("COMPLETE")
print("=" * 70)

print(
    f"Amavasya/Purnima events: "
    f"{len(events):,}"
)

print(
    f"Transition intervals: "
    f"{len(transitions):,}"
)
