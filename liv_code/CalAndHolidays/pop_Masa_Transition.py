from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import swisseph as swe

from sqlalchemy import create_engine, text


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

CALENDAR_SYSTEM = "Amanta"


# ============================================================
# DATE RANGE
# ============================================================

START_DATE = datetime(
    1926,
    1,
    1,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)

END_DATE = datetime(
    2126,
    1,
    1,
    0,
    0,
    0,
    tzinfo=timezone.utc,
)


# ============================================================
# SWISS EPHEMERIS
# ============================================================

swe.set_sid_mode(swe.SIDM_LAHIRI)

FLAGS = (
    swe.FLG_SWIEPH
    | swe.FLG_SPEED
    | swe.FLG_SIDEREAL
)


# ============================================================
# MASA REFERENCE
# ============================================================

MASA = {
    1: ("Chaitra",      "चैत्र"),
    2: ("Vaishakha",    "वैशाख"),
    3: ("Jyeshtha",     "ज्येष्ठ"),
    4: ("Ashadha",      "आषाढ़"),
    5: ("Shravana",     "श्रावण"),
    6: ("Bhadrapada",   "भाद्रपद"),
    7: ("Ashwin",       "आश्विन"),
    8: ("Kartika",      "कार्तिक"),
    9: ("Margashirsha", "मार्गशीर्ष"),
    10: ("Pausha",      "पौष"),
    11: ("Magha",       "माघ"),
    12: ("Phalguna",    "फाल्गुन"),
}


# ============================================================
# SQLALCHEMY
# ============================================================

engine = create_engine(
    DATABASE_URL,
    echo=False,
)


# ============================================================
# JULIAN DAY
# ============================================================

def datetime_to_jd(dt: datetime) -> float:

    dt = dt.astimezone(timezone.utc)

    hour = (
        dt.hour
        + dt.minute / 60.0
        + dt.second / 3600.0
        + dt.microsecond / 3_600_000_000.0
    )

    return swe.julday(
        dt.year,
        dt.month,
        dt.day,
        hour,
    )


def jd_to_datetime_utc(jd: float) -> datetime:

    year, month, day, hour = swe.revjul(
        jd,
        swe.GREG_CAL,
    )

    hour_int = int(hour)

    minute_float = (
        hour - hour_int
    ) * 60.0

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

    if microsecond >= 1_000_000:

        second_int += 1
        microsecond -= 1_000_000

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


# ============================================================
# SUN / MOON
# ============================================================

def get_sun_moon(jd_ut: float):

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
# LUNAR PHASE
# ============================================================

def lunar_phase(jd_ut: float) -> float:

    sun, moon = get_sun_moon(jd_ut)

    return (
        moon - sun
    ) % 360.0


# ============================================================
# FIND EXACT AMAVASYA
# ============================================================

def refine_amavasya(
    left_jd: float,
    right_jd: float,
) -> float:
    """
    Refine a known 360 -> 0 phase crossing.
    """

    for _ in range(50):

        middle_jd = (
            left_jd + right_jd
        ) / 2.0

        left_phase = lunar_phase(
            left_jd
        )

        middle_phase = lunar_phase(
            middle_jd
        )

        # Crossing is 360 -> 0.
        if middle_phase >= left_phase:

            left_jd = middle_jd

        else:

            right_jd = middle_jd

    return (
        left_jd + right_jd
    ) / 2.0


# ============================================================
# FIND AMAVASYAS FROM EXISTING 12-HOUR DATA
# ============================================================

def find_amavasyas():

    sql = text(
        """
        SELECT
            Date_Time_UTC,
            Angular_Separation
        FROM Sun_Moon_Position
        WHERE Location = :location
          AND Date_Time_UTC >= :start
          AND Date_Time_UTC < :end
        ORDER BY Date_Time_UTC
        """
    )

    with engine.connect() as connection:

        records = connection.execute(
            sql,
            {
                "location": LOCATION,
                "start":
                    START_DATE.isoformat(),
                "end":
                    END_DATE.isoformat(),
            },
        ).fetchall()

    print(
        f"Loaded {len(records):,} "
        "12-hour astronomical observations."
    )

    amavasyas = []

    previous_dt = None
    previous_phase = None

    for row in records:

        dt = datetime.fromisoformat(
            row[0]
        )

        phase = float(row[1])

        if (
            previous_phase is not None
            and phase < previous_phase
        ):

            left_jd = datetime_to_jd(
                previous_dt
            )

            right_jd = datetime_to_jd(
                dt
            )

            amavasya_jd = refine_amavasya(
                left_jd,
                right_jd,
            )

            amavasya = jd_to_datetime_utc(
                amavasya_jd
            )

            amavasyas.append(
                amavasya
            )

        previous_dt = dt
        previous_phase = phase

    return amavasyas


# ============================================================
# SUN LONGITUDE
# ============================================================

def sun_longitude(jd_ut: float) -> float:

    result, _ = swe.calc_ut(
        jd_ut,
        swe.SUN,
        FLAGS,
    )

    return result[0] % 360.0


# ============================================================
# FIND SANKRANTI BETWEEN TWO TIMES
# ============================================================


def find_sankrantis(
    start_dt: datetime,
    end_dt: datetime,
):
    """
    Find every sidereal Sun sign boundary
    between two Amavasyas.

    The search is performed in an unwrapped
    longitude coordinate, so Pisces -> Aries
    (360° -> 0°) is handled correctly.
    """

    start_jd = datetime_to_jd(start_dt)
    end_jd = datetime_to_jd(end_dt)

    start_lon = sun_longitude(start_jd)
    end_lon = sun_longitude(end_jd)

    # Forward angular movement of the Sun.
    total_motion = (
        end_lon - start_lon
    ) % 360.0

    crossings = []

    # First 30-degree boundary after start_lon.
    first_boundary = (
        (int(start_lon // 30.0) + 1) * 30.0
    )

    boundary = first_boundary

    while boundary <= start_lon + total_motion:

        target_distance = (
            boundary - start_lon
        )

        left = start_jd
        right = end_jd

        for _ in range(60):

            middle = (
                left + right
            ) / 2.0

            middle_lon = sun_longitude(
                middle
            )

            middle_distance = (
                middle_lon - start_lon
            ) % 360.0

            if middle_distance < target_distance:
                left = middle
            else:
                right = middle

        crossing_jd = (
            left + right
        ) / 2.0

        target_lon = boundary % 360.0

        crossings.append(
            (
                jd_to_datetime_utc(
                    crossing_jd
                ),
                int(target_lon // 30.0),
            )
        )

        boundary += 30.0

    return crossings

# ============================================================
# MASA FROM SANKRANTI
# ============================================================

def masa_from_sankranti(
    sankranti_sign: int,
) -> int:
    """
    Sun's sidereal sign:

        Aries       -> Chaitra
        Taurus      -> Vaishakha
        ...
        Pisces      -> Phalguna

    sign is zero-based.
    """

    return (
        sankranti_sign + 1
    )


# ============================================================
# POPULATE MASA
# ============================================================

def populate_masa():

    print()
    print("=" * 70)
    print("Creating Masa_Transition")
    print("=" * 70)

    print(
        "Calendar:",
        CALENDAR_SYSTEM,
    )

    print(
        "Location:",
        LOCATION,
    )

    print()

    # --------------------------------------------------------
    # Find Amavasyas
    # --------------------------------------------------------

    amavasyas = find_amavasyas()

    print(
        f"Found {len(amavasyas):,} Amavasyas."
    )

    print()

    # --------------------------------------------------------
    # Need an Amavasya before the requested
    # start and one after the requested end.
    # --------------------------------------------------------

    intervals = []

    for i in range(
        len(amavasyas) - 1
    ):

        start_amavasya = (
            amavasyas[i]
        )

        end_amavasya = (
            amavasyas[i + 1]
        )

        if (
            end_amavasya <= START_DATE
            or start_amavasya >= END_DATE
        ):
            continue

        intervals.append(
            (
                start_amavasya,
                end_amavasya,
            )
        )

    # --------------------------------------------------------
    # SQL
    # --------------------------------------------------------

    insert_sql = text(
        """
        INSERT OR REPLACE INTO Masa_Transition
        (
            Start_Date_Time_UTC,
            End_Date_Time_UTC,

            Start_Date_Time_Local,
            End_Date_Time_Local,

            Location,
            Calendar_System,

            Masa_Number,
            Masa_English,
            Masa_Hindi,

            Masa_Type
        )
        VALUES
        (
            :start_utc,
            :end_utc,

            :start_local,
            :end_local,

            :location,
            :calendar_system,

            :masa_number,
            :masa_english,
            :masa_hindi,

            :masa_type
        )
        """
    )

    rows = []

    normal_count = 0
    adhika_count = 0
    kshaya_count = 0

    # --------------------------------------------------------
    # Process lunar months
    # --------------------------------------------------------

    for (
        start_amavasya,
        end_amavasya,
    ) in intervals:

        sankrantis = find_sankrantis(
            start_amavasya,
            end_amavasya,
        )

        sankranti_count = len(
            sankrantis
        )

        # ----------------------------------------------------
        # Determine Masa
        # ----------------------------------------------------

        if sankranti_count == 0:

            # ------------------------------------------------
            # No solar sign transition:
            # Adhika Masa.
            #
            # The month repeats the previous
            # month's name.
            # ------------------------------------------------

            masa_type = "Adhika"

            adhika_count += 1

            # Find previous interval's name.
            previous_sankrantis = []

            if len(rows) > 0:

                masa_number = int(
                    rows[-1]["masa_number"]
                )

            else:

                # This should only occur if the
                # requested range starts before
                # the first available Masa.
                continue

        elif sankranti_count == 1:

            # ------------------------------------------------
            # Normal lunar month.
            # ------------------------------------------------

            masa_type = "Normal"

            normal_count += 1

            (
                sankranti_dt,
                sign,
            ) = sankrantis[0]

            masa_number = (
                masa_from_sankranti(sign)
            )

        else:

            # ------------------------------------------------
            # Rare Kshaya situation.
            # ------------------------------------------------

            masa_type = "Kshaya"

            kshaya_count += 1

            # Use the first Sankranti for the
            # primary month assignment.
            (
                sankranti_dt,
                sign,
            ) = sankrantis[0]

            masa_number = (
                masa_from_sankranti(sign)
            )

        masa_english, masa_hindi = MASA[
            masa_number
        ]

        start_local = (
            start_amavasya.astimezone(
                TIMEZONE
            )
        )

        end_local = (
            end_amavasya.astimezone(
                TIMEZONE
            )
        )

        rows.append(
            {
                "start_utc":
                    start_amavasya.isoformat(),

                "end_utc":
                    end_amavasya.isoformat(),

                "start_local":
                    start_local.isoformat(),

                "end_local":
                    end_local.isoformat(),

                "location":
                    LOCATION,

                "calendar_system":
                    CALENDAR_SYSTEM,

                "masa_number":
                    f"{masa_number:02d}",

                "masa_english":
                    masa_english,

                "masa_hindi":
                    masa_hindi,

                "masa_type":
                    masa_type,
            }
        )

    # --------------------------------------------------------
    # Insert
    # --------------------------------------------------------

    with engine.begin() as connection:

        connection.execute(
            insert_sql,
            rows,
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)

    print(
        f"Normal Masa : {normal_count:,}"
    )

    print(
        f"Adhika Masa : {adhika_count:,}"
    )

    print(
        f"Kshaya Masa : {kshaya_count:,}"
    )

    print(
        f"Total rows  : {len(rows):,}"
    )

    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    populate_masa()

    print()
    print(
        "Masa_Transition populated successfully."
    )
