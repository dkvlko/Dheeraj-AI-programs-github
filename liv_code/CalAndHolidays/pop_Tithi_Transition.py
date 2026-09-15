from datetime import (
    date,
    datetime,
    timedelta,
)
from zoneinfo import ZoneInfo

import swisseph as swe

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    PrimaryKeyConstraint,
)

from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
)


# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = (
    "sqlite:////data/BLOBS/CalAndHolidays/CalAndHolidays.db"
)


# ============================================================
# LOCATION
# ============================================================

LOCATION = "Lucknow, Uttar Pradesh, India"
LATITUDE = 26.8467
LONGITUDE = 80.9462

TIMEZONE = ZoneInfo("Asia/Kolkata")


# ============================================================
# DATE RANGE
# ============================================================

START_DATE = date(1926, 1, 1)
END_DATE = date(2126, 12, 31)


# ============================================================
# SWISS EPHEMERIS
# ============================================================

# Lahiri ayanamsha
swe.set_sid_mode(swe.SIDM_LAHIRI)

FLAGS = (
    swe.FLG_SWIEPH
    | swe.FLG_SPEED
    | swe.FLG_SIDEREAL
)


# ============================================================
# SQLALCHEMY
# ============================================================

class Base(DeclarativeBase):
    pass


class TithiTransition(Base):

    __tablename__ = "Tithi_Transition"

    Start_Date_Time_UTC = Column(
        String,
        nullable=False,
    )

    End_Date_Time_UTC = Column(
        String,
        nullable=False,
    )

    Start_Date_Time_Local = Column(
        String,
        nullable=False,
    )

    End_Date_Time_Local = Column(
        String,
        nullable=False,
    )

    Location = Column(
        String,
        nullable=False,
    )

    Latitude = Column(
        Float,
        nullable=False,
    )

    Longitude = Column(
        Float,
        nullable=False,
    )

    Angular_Separation_Start = Column(
        Float,
        nullable=False,
    )

    Angular_Separation_End = Column(
        Float,
        nullable=False,
    )

    Tithi = Column(
        String,
        nullable=False,
    )

    Paksha = Column(
        String,
        nullable=False,
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "Start_Date_Time_UTC",
            "Location",
        ),
    )


engine = create_engine(
    DATABASE_URL,
    echo=False,
)

Base.metadata.create_all(engine)


# ============================================================
# SUN + MOON LONGITUDE
# ============================================================

def sun_moon_longitudes(jd_ut):
    """
    Return geocentric sidereal Sun and Moon longitudes
    using Lahiri ayanamsha.
    """

    sun, _ = swe.calc_ut(
        jd_ut,
        swe.SUN,
        FLAGS,
    )

    moon, _ = swe.calc_ut(
        jd_ut,
        swe.MOON,
        FLAGS,
    )

    return (
        sun[0] % 360.0,
        moon[0] % 360.0,
    )


# ============================================================
# ANGULAR SEPARATION
# ============================================================

def angular_separation(jd_ut):
    """
    Return Moon-Sun angular separation in the range
    0 <= separation < 360 degrees.
    """

    sun_longitude, moon_longitude = (
        sun_moon_longitudes(jd_ut)
    )

    return (
        (moon_longitude - sun_longitude) % 360.0
    )


# ============================================================
# DATETIME -> JULIAN DAY
# ============================================================

def datetime_to_jd(dt_utc):

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
    )


# ============================================================
# JULIAN DAY -> UTC DATETIME
# ============================================================

def jd_to_datetime_utc(jd):

    year, month, day, hour = swe.revjul(
        jd,
        swe.GREG_CAL,
    )

    hour_int = int(hour)

    minutes_float = (
        hour - hour_int
    ) * 60.0

    minute = int(minutes_float)

    seconds_float = (
        minutes_float - minute
    ) * 60.0

    second = int(seconds_float)

    microsecond = int(
        (seconds_float - second)
        * 1_000_000
    )

    # Protect against floating-point rounding such as
    # 59.999999999 becoming an invalid microsecond value.
    if microsecond >= 1_000_000:
        second += 1
        microsecond -= 1_000_000

    return datetime(
        year,
        month,
        day,
        hour_int,
        minute,
        second,
        microsecond,
        tzinfo=ZoneInfo("UTC"),
    )


# ============================================================
# TITHI NUMBER / PAKSHA
# ============================================================

def tithi_info(separation):
    """
    Convert angular separation to:
        Tithi: 01..15
        Paksha: Shukla / Krishna
    """

    # 0..179.999... = Shukla
    # 180..359.999... = Krishna

    if separation < 180.0:
        tithi_number = int(
            separation // 12.0
        ) + 1
        paksha = "Shukla"
    else:
        tithi_number = int(
            (separation - 180.0) // 12.0
        ) + 1
        paksha = "Krishna"

    return (
        f"{tithi_number:02d}",
        paksha,
    )


# ============================================================
# FIND NEXT TITHI BOUNDARY
# ============================================================

def find_next_boundary(
    jd_start,
    separation_start,
):
    """
    Find the next 12-degree angular-separation boundary.

    The Moon-Sun relative longitude increases through
    360 degrees repeatedly, so the next boundary is one
    of 0, 12, 24, ..., 348 degrees.

    Returns:
        jd_boundary
        boundary_separation
    """

    # Current tithi index in the 30-tithi cycle.
    current_index = int(
        separation_start // 12.0
    )

    next_index = current_index + 1

    if next_index >= 30:
        next_index = 0

    boundary_separation = (
        next_index * 12.0
    )

    distance = (
        boundary_separation
        - separation_start
    ) % 360.0

    # Estimate relative Sun-Moon speed.
    sun_start, moon_start = (
        swe.calc_ut(
            jd_start,
            swe.SUN,
            FLAGS,
        )[0],
        swe.calc_ut(
            jd_start,
            swe.MOON,
            FLAGS,
        )[0],
    )

    relative_speed = (
        moon_start[3]
        - sun_start[3]
    )

    # Normally positive and around 12 deg/day.
    if relative_speed <= 0:
        relative_speed = 12.0

    estimated_days = (
        distance / relative_speed
    )

    jd_low = jd_start

    jd_high = (
        jd_start
        + max(
            0.05,
            estimated_days * 1.5,
        )
    )

    # Make sure the boundary has actually been crossed.
    while True:

        separation_high = angular_separation(
            jd_high
        )

        travelled = (
            separation_high
            - separation_start
        ) % 360.0

        if travelled >= distance:
            break

        jd_high += 0.25

    # --------------------------------------------------------
    # Binary search
    # --------------------------------------------------------

    for _ in range(60):

        jd_mid = (
            jd_low + jd_high
        ) / 2.0

        separation_mid = angular_separation(
            jd_mid
        )

        travelled = (
            separation_mid
            - separation_start
        ) % 360.0

        if travelled >= distance:
            jd_high = jd_mid
        else:
            jd_low = jd_mid

    return (
        jd_high,
        boundary_separation,
    )


# ============================================================
# BUILD TRANSITIONS
# ============================================================

start_local = datetime.combine(
    START_DATE,
    datetime.min.time(),
).replace(
    tzinfo=TIMEZONE,
)

end_local = datetime.combine(
    END_DATE + timedelta(days=1),
    datetime.min.time(),
).replace(
    tzinfo=TIMEZONE,
)

start_utc = start_local.astimezone(
    ZoneInfo("UTC"),
)

end_utc = end_local.astimezone(
    ZoneInfo("UTC"),
)

jd_current = datetime_to_jd(
    start_utc,
)

jd_end = datetime_to_jd(
    end_utc,
)


transitions = []


while jd_current < jd_end:

    separation_start = angular_separation(
        jd_current
    )

    tithi, paksha = tithi_info(
        separation_start
    )

    (
        jd_boundary,
        boundary_separation,
    ) = find_next_boundary(
        jd_current,
        separation_start,
    )

    # Don't store transitions beyond requested period.
    if jd_boundary > jd_end:
        break

    start_dt_utc = jd_to_datetime_utc(
        jd_current
    )

    end_dt_utc = jd_to_datetime_utc(
        jd_boundary
    )

    start_dt_local = (
        start_dt_utc.astimezone(TIMEZONE)
    )

    end_dt_local = (
        end_dt_utc.astimezone(TIMEZONE)
    )

    transitions.append(
        {
            "start_utc": start_dt_utc,
            "end_utc": end_dt_utc,
            "start_local": start_dt_local,
            "end_local": end_dt_local,
            "separation_start": separation_start,
            "separation_end": boundary_separation,
            "tithi": tithi,
            "paksha": paksha,
        }
    )

    print(
        f"{start_dt_local:%Y-%m-%d %H:%M:%S} "
        f"-> "
        f"{end_dt_local:%Y-%m-%d %H:%M:%S}  "
        f"Separation: "
        f"{separation_start:.6f}° -> "
        f"{boundary_separation:.6f}°  "
        f"Tithi: {tithi} {paksha}"
    )

    # Continue exactly at the transition.
    jd_current = jd_boundary


# ============================================================
# DATABASE INSERT
# ============================================================

with Session(engine) as session:

    inserted = 0

    for item in transitions:

        start_utc_string = (
            item["start_utc"]
            .strftime("%Y-%m-%d %H:%M:%S")
        )

        end_utc_string = (
            item["end_utc"]
            .strftime("%Y-%m-%d %H:%M:%S")
        )

        start_local_string = (
            item["start_local"]
            .strftime("%Y-%m-%d %H:%M:%S")
        )

        end_local_string = (
            item["end_local"]
            .strftime("%Y-%m-%d %H:%M:%S")
        )

        existing = session.get(
            TithiTransition,
            (
                start_utc_string,
                LOCATION,
            ),
        )

        if existing is None:

            row = TithiTransition(
                Start_Date_Time_UTC=(
                    start_utc_string
                ),

                End_Date_Time_UTC=(
                    end_utc_string
                ),

                Start_Date_Time_Local=(
                    start_local_string
                ),

                End_Date_Time_Local=(
                    end_local_string
                ),

                Location=LOCATION,

                Latitude=LATITUDE,

                Longitude=LONGITUDE,

                Angular_Separation_Start=(
                    item["separation_start"]
                ),

                Angular_Separation_End=(
                    item["separation_end"]
                ),

                Tithi=item["tithi"],

                Paksha=item["paksha"],
            )

            session.add(row)
            inserted += 1

    session.commit()


print()
print("=" * 80)
print(
    f"{len(transitions)} Tithi transitions calculated."
)
print(
    f"{inserted} new Tithi transitions inserted successfully."
)
print("=" * 80)
