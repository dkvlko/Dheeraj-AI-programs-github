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

TIMEZONE = ZoneInfo("Asia/Kolkata")


# ============================================================
# DATE RANGE
# ============================================================

START_DATE = date(1926, 9, 11)
END_DATE = date(2126, 9, 17)


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
# YOGA REFERENCE DATA
# ============================================================

YOGAS = [
    ("01", "Vishkambha", "विष्कम्भ"),
    ("02", "Priti",      "प्रीति"),
    ("03", "Ayushman",   "आयुष्मान"),
    ("04", "Saubhagya",  "सौभाग्य"),
    ("05", "Shobhana",   "शोभन"),
    ("06", "Atiganda",   "अतिगण्ड"),
    ("07", "Sukarma",    "सुकर्म"),
    ("08", "Dhriti",     "धृति"),
    ("09", "Shula",      "शूल"),
    ("10", "Ganda",      "गण्ड"),
    ("11", "Vriddhi",    "वृद्धि"),
    ("12", "Dhruva",     "ध्रुव"),
    ("13", "Vyaghata",   "व्याघात"),
    ("14", "Harshana",   "हर्षण"),
    ("15", "Vajra",      "वज्र"),
    ("16", "Siddhi",     "सिद्धि"),
    ("17", "Vyatipata",  "व्यतीपात"),
    ("18", "Variyana",   "वरीयान"),
    ("19", "Parigha",    "परिघ"),
    ("20", "Shiva",      "शिव"),
    ("21", "Siddha",     "सिद्ध"),
    ("22", "Sadhya",     "साध्य"),
    ("23", "Shubha",     "शुभ"),
    ("24", "Shukla",     "शुक्ल"),
    ("25", "Brahma",     "ब्रह्म"),
    ("26", "Indra",      "इन्द्र"),
    ("27", "Vaidhriti",  "वैधृति"),
]


YOGA_SIZE = 360.0 / 27.0
# 13°20' = 13.333333333333...


# ============================================================
# SQLALCHEMY
# ============================================================

class Base(DeclarativeBase):
    pass


class YogaTransition(Base):

    __tablename__ = "Yoga_Transition"

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

    Sun_Longitude_Start = Column(
        Float,
        nullable=False,
    )

    Moon_Longitude_Start = Column(
        Float,
        nullable=False,
    )

    Yoga_Longitude_Start = Column(
        Float,
        nullable=False,
    )

    Sun_Longitude_End = Column(
        Float,
        nullable=False,
    )

    Moon_Longitude_End = Column(
        Float,
        nullable=False,
    )

    Yoga_Longitude_End = Column(
        Float,
        nullable=False,
    )

    Yoga_Number = Column(
        String,
        nullable=False,
    )

    Yoga = Column(
        String,
        nullable=False,
    )

    SanskritName = Column(
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
# SUN + MOON LONGITUDES
# ============================================================

def get_sun_moon_longitudes(jd_ut):

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

    sun_longitude = sun_position[0] % 360.0
    moon_longitude = moon_position[0] % 360.0

    return (
        sun_longitude,
        moon_longitude,
    )


# ============================================================
# YOGA LONGITUDE
# ============================================================

def get_yoga_longitude(
    sun_longitude,
    moon_longitude,
):
    """
    Yoga longitude = Sun + Moon,
    normalized to 0° ... <360°.
    """

    return (
        sun_longitude
        + moon_longitude
    ) % 360.0


# ============================================================
# YOGA NUMBER
# ============================================================

def get_yoga_index(yoga_longitude):

    index = int(
        yoga_longitude // YOGA_SIZE
    )

    if index >= 27:
        index = 26

    return index


# ============================================================
# DATETIME → JULIAN DAY
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
# JULIAN DAY → UTC DATETIME
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
# YOGA VALUE AT JULIAN DAY
# ============================================================

def yoga_at_jd(jd):

    (
        sun_longitude,
        moon_longitude,
    ) = get_sun_moon_longitudes(jd)

    yoga_longitude = get_yoga_longitude(
        sun_longitude,
        moon_longitude,
    )

    return (
        sun_longitude,
        moon_longitude,
        yoga_longitude,
    )


# ============================================================
# FIND NEXT YOGA BOUNDARY
# ============================================================

def find_next_yoga_boundary(
    jd_start,
    yoga_longitude_start,
):
    """
    Find the next 13°20' Yoga boundary.

    Binary-search the actual Sun+Moon longitude
    rather than assuming constant angular velocity.
    """

    current_index = get_yoga_index(
        yoga_longitude_start
    )

    next_index = current_index + 1

    if next_index >= 27:
        next_index = 0

    boundary_longitude = (
        next_index * YOGA_SIZE
    )

    distance = (
        boundary_longitude
        - yoga_longitude_start
    ) % 360.0

    # --------------------------------------------------------
    # Estimate Yoga speed.
    # --------------------------------------------------------

    sun_position, _ = swe.calc_ut(
        jd_start,
        swe.SUN,
        FLAGS,
    )

    moon_position, _ = swe.calc_ut(
        jd_start,
        swe.MOON,
        FLAGS,
    )

    sun_speed = sun_position[3]
    moon_speed = moon_position[3]

    yoga_speed = (
        sun_speed + moon_speed
    )

    if yoga_speed <= 0:
        yoga_speed = 14.0

    estimated_days = (
        distance / yoga_speed
    )

    # Initial bracket.
    jd_low = jd_start

    jd_high = (
        jd_start
        + max(
            0.05,
            estimated_days * 1.5,
        )
    )

    # --------------------------------------------------------
    # Expand until boundary is crossed.
    # --------------------------------------------------------

    while True:

        (
            _sun,
            _moon,
            yoga_high,
        ) = yoga_at_jd(jd_high)

        travelled = (
            yoga_high
            - yoga_longitude_start
        ) % 360.0

        if travelled >= distance:
            break

        jd_high += 0.25

    # --------------------------------------------------------
    # Binary search.
    # --------------------------------------------------------

    for _ in range(60):

        jd_mid = (
            jd_low + jd_high
        ) / 2.0

        (
            _sun,
            _moon,
            yoga_mid,
        ) = yoga_at_jd(jd_mid)

        travelled = (
            yoga_mid
            - yoga_longitude_start
        ) % 360.0

        if travelled >= distance:
            jd_high = jd_mid
        else:
            jd_low = jd_mid

    return (
        jd_high,
        boundary_longitude,
    )


# ============================================================
# DATE RANGE → JULIAN DAYS
# ============================================================

start_local = datetime.combine(
    START_DATE,
    datetime.min.time(),
).replace(
    tzinfo=TIMEZONE
)

end_local = datetime.combine(
    END_DATE + timedelta(days=1),
    datetime.min.time(),
).replace(
    tzinfo=TIMEZONE
)

start_utc = start_local.astimezone(
    ZoneInfo("UTC")
)

end_utc = end_local.astimezone(
    ZoneInfo("UTC")
)

jd_current = datetime_to_jd(
    start_utc
)

jd_end = datetime_to_jd(
    end_utc
)


# ============================================================
# FIND TRANSITIONS
# ============================================================

transitions = []


while jd_current < jd_end:

    (
        sun_start,
        moon_start,
        yoga_start,
    ) = yoga_at_jd(
        jd_current
    )

    index = get_yoga_index(
        yoga_start
    )

    (
        yoga_number,
        yoga_name,
        sanskrit_name,
    ) = YOGAS[index]

    (
        jd_boundary,
        yoga_boundary,
    ) = find_next_yoga_boundary(
        jd_current,
        yoga_start,
    )

    if jd_boundary > jd_end:
        break

    (
        sun_end,
        moon_end,
        yoga_end,
    ) = yoga_at_jd(
        jd_boundary
    )

    start_dt_utc = jd_to_datetime_utc(
        jd_current
    )

    end_dt_utc = jd_to_datetime_utc(
        jd_boundary
    )

    start_dt_local = (
        start_dt_utc.astimezone(
            TIMEZONE
        )
    )

    end_dt_local = (
        end_dt_utc.astimezone(
            TIMEZONE
        )
    )

    transitions.append(
        {
            "start_utc": start_dt_utc,
            "end_utc": end_dt_utc,

            "start_local": start_dt_local,
            "end_local": end_dt_local,

            "sun_start": sun_start,
            "moon_start": moon_start,
            "yoga_start": yoga_start,

            "sun_end": sun_end,
            "moon_end": moon_end,
            "yoga_end": yoga_end,

            "number": yoga_number,
            "name": yoga_name,
            "sanskrit": sanskrit_name,
        }
    )

    print(
        f"{start_dt_local:%Y-%m-%d %H:%M:%S}"
        f" → "
        f"{end_dt_local:%Y-%m-%d %H:%M:%S}  "
        f"Sun={sun_start:10.6f}°  "
        f"Moon={moon_start:10.6f}°  "
        f"YogaSum={yoga_start:10.6f}°  "
        f"{yoga_number} "
        f"{yoga_name} "
        f"({sanskrit_name})"
    )

    # Continue from the exact transition.
    jd_current = jd_boundary


# ============================================================
# INSERT INTO DATABASE
# ============================================================

with Session(engine) as session:

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
            YogaTransition,
            (
                start_utc_string,
                LOCATION,
            ),
        )

        if existing is None:

            row = YogaTransition(
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

                Sun_Longitude_Start=(
                    item["sun_start"]
                ),

                Moon_Longitude_Start=(
                    item["moon_start"]
                ),

                Yoga_Longitude_Start=(
                    item["yoga_start"]
                ),

                Sun_Longitude_End=(
                    item["sun_end"]
                ),

                Moon_Longitude_End=(
                    item["moon_end"]
                ),

                Yoga_Longitude_End=(
                    item["yoga_end"]
                ),

                Yoga_Number=item["number"],

                Yoga=item["name"],

                SanskritName=item["sanskrit"],
            )

            session.add(row)

    session.commit()


print()
print(
    f"{len(transitions)} Yoga transitions "
    "inserted successfully."
)
