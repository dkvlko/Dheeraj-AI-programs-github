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
# NAKSHATRA REFERENCE
# ============================================================

NAKSHATRAS = [
    ("01", "Ashwini",           "अश्विनी"),
    ("02", "Bharani",           "भरणी"),
    ("03", "Krittika",          "कृत्तिका"),
    ("04", "Rohini",            "रोहिणी"),
    ("05", "Mrigashira",        "मृगशिरा"),
    ("06", "Ardra",             "आर्द्रा"),
    ("07", "Punarvasu",         "पुनर्वसु"),
    ("08", "Pushya",            "पुष्य"),
    ("09", "Ashlesha",          "आश्लेषा"),
    ("10", "Magha",             "मघा"),
    ("11", "Purva Phalguni",    "पूर्वाफाल्गुनी"),
    ("12", "Uttara Phalguni",   "उत्तराफाल्गुनी"),
    ("13", "Hasta",             "हस्त"),
    ("14", "Chitra",             "चित्रा"),
    ("15", "Swati",              "स्वाती"),
    ("16", "Vishakha",           "विशाखा"),
    ("17", "Anuradha",           "अनुराधा"),
    ("18", "Jyeshtha",           "ज्येष्ठा"),
    ("19", "Mula",               "मूला"),
    ("20", "Purva Ashadha",      "पूर्वाषाढा"),
    ("21", "Uttara Ashadha",     "उत्तराषाढा"),
    ("22", "Shravana",           "श्रवणा"),
    ("23", "Dhanishtha",         "धनिष्ठा"),
    ("24", "Shatabhisha",        "शतभिषा"),
    ("25", "Purva Bhadrapada",   "पूर्वाभाद्रपदा"),
    ("26", "Uttara Bhadrapada",  "उत्तराभाद्रपदा"),
    ("27", "Revati",             "रेवती"),
]


NAKSHATRA_SIZE = 360.0 / 27.0
# 13°20' = 13.333333333333...


# ============================================================
# SQLALCHEMY
# ============================================================

class Base(DeclarativeBase):
    pass


class NakshatraTransition(Base):

    __tablename__ = "Nakshatra_Transition"

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

    Moon_Longitude_Start = Column(
        Float,
        nullable=False,
    )

    Moon_Longitude_End = Column(
        Float,
        nullable=False,
    )

    Nakshatra_Number = Column(
        String,
        nullable=False,
    )

    Nakshatra = Column(
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
# MOON LONGITUDE
# ============================================================

def moon_longitude(jd_ut):
    """
    Return geocentric sidereal Moon longitude
    using Lahiri ayanamsha.
    """

    position, _ = swe.calc_ut(
        jd_ut,
        swe.MOON,
        FLAGS,
    )

    return position[0] % 360.0


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
# NAKSHATRA INDEX
# ============================================================

def nakshatra_index(longitude):

    index = int(
        longitude // NAKSHATRA_SIZE
    )

    if index >= 27:
        index = 26

    return index


# ============================================================
# FIND NEXT NAKSHATRA BOUNDARY
# ============================================================

def find_next_boundary(
    jd_start,
    current_longitude,
):
    """
    Find the next 13°20' Nakshatra boundary.

    Returns:
        jd_boundary
        boundary_longitude
    """

    current_index = nakshatra_index(
        current_longitude
    )

    next_index = current_index + 1

    if next_index >= 27:
        next_index = 0

    boundary_longitude = (
        next_index * NAKSHATRA_SIZE
    )

    # Estimate initial time using Moon speed.
    position, _ = swe.calc_ut(
        jd_start,
        swe.MOON,
        FLAGS,
    )

    moon_speed = position[3]

    if moon_speed <= 0:
        moon_speed = 13.0

    distance = (
        boundary_longitude
        - current_longitude
    ) % 360.0

    estimated_days = (
        distance / moon_speed
    )

    # Start around the estimated crossing.
    jd_low = jd_start
    jd_high = (
        jd_start
        + max(0.1, estimated_days * 1.5)
    )

    # Make sure the boundary has actually been crossed.
    while True:

        longitude_high = moon_longitude(
            jd_high
        )

        travelled = (
            longitude_high
            - current_longitude
        ) % 360.0

        if travelled >= distance:
            break

        jd_high += 0.5

    # --------------------------------------------------------
    # Binary search
    # --------------------------------------------------------

    for _ in range(50):

        jd_mid = (
            jd_low + jd_high
        ) / 2.0

        longitude_mid = moon_longitude(
            jd_mid
        )

        travelled = (
            longitude_mid
            - current_longitude
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
# MAIN
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


transitions = []


while jd_current < jd_end:

    longitude_start = moon_longitude(
        jd_current
    )

    index = nakshatra_index(
        longitude_start
    )

    (
        number,
        name,
        sanskrit_name,
    ) = NAKSHATRAS[index]

    (
        jd_boundary,
        boundary_longitude,
    ) = find_next_boundary(
        jd_current,
        longitude_start,
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
            "longitude_start": longitude_start,
            "longitude_end": boundary_longitude,
            "number": number,
            "name": name,
            "sanskrit": sanskrit_name,
        }
    )

    print(
        f"{start_dt_local:%Y-%m-%d %H:%M:%S} "
        f"→ "
        f"{end_dt_local:%Y-%m-%d %H:%M:%S}  "
        f"Moon: "
        f"{longitude_start:.6f}° → "
        f"{boundary_longitude:.6f}°  "
        f"{number} {name} ({sanskrit_name})"
    )

    # Continue exactly at the transition.
    jd_current = jd_boundary


# ============================================================
# DATABASE INSERT
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
            NakshatraTransition,
            (
                start_utc_string,
                LOCATION,
            ),
        )

        if existing is None:

            row = NakshatraTransition(
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

                Moon_Longitude_Start=(
                    item["longitude_start"]
                ),

                Moon_Longitude_End=(
                    item["longitude_end"]
                ),

                Nakshatra_Number=(
                    item["number"]
                ),

                Nakshatra=(
                    item["name"]
                ),

                SanskritName=(
                    item["sanskrit"]
                ),
            )

            session.add(row)

    session.commit()


print()
print(
    f"{len(transitions)} Nakshatra transitions "
    "inserted successfully."
)
