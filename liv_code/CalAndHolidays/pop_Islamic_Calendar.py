from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import sqlite3
import math

import swisseph as swe


# ============================================================
# Configuration
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"
LATITUDE = 26.8467
LONGITUDE = 80.9462
TIMEZONE = ZoneInfo("Asia/Kolkata")

START_YEAR = 2026
END_YEAR = 2027

# ------------------------------------------------------------
# Astronomical Hilal criterion
# ------------------------------------------------------------

MIN_MOON_AGE_HOURS = 18.0
MIN_ELONGATION_DEGREES = 10.0
MIN_MOONSET_LAG_MINUTES = 45.0

VISIBILITY_RULE = (
    "Age>=18h AND Elongation>=10deg "
    "AND MoonsetLag>=45min"
)


# ============================================================
# Islamic month names
# ============================================================

MONTH_NAMES = {
    1: ("Muharram", "مُحَرَّم"),
    2: ("Safar", "صَفَر"),
    3: ("Rabi al-Awwal", "رَبِيع الأَوَّل"),
    4: ("Rabi al-Thani", "رَبِيع الثَّانِي"),
    5: ("Jumada al-Awwal", "جُمَادَى الأَوَّل"),
    6: ("Jumada al-Thani", "جُمَادَى الثَّانِي"),
    7: ("Rajab", "رَجَب"),
    8: ("Shaban", "شَعْبَان"),
    9: ("Ramadan", "رَمَضَان"),
    10: ("Shawwal", "شَوَّال"),
    11: ("Dhul-Qadah", "ذُو القَعْدَة"),
    12: ("Dhul-Hijjah", "ذُو الحِجَّة"),
}


# ============================================================
# Database
# ============================================================

def get_connection():
    return sqlite3.connect(DB_PATH)


def create_table(conn):

    conn.execute("""
        CREATE TABLE IF NOT EXISTS Islamic_Calendar (
            Hijri_Year INTEGER NOT NULL,
            Hijri_Month INTEGER NOT NULL
                CHECK (Hijri_Month BETWEEN 1 AND 12),

            Hijri_Day INTEGER NOT NULL
                CHECK (Hijri_Day BETWEEN 1 AND 30),

            Gregorian_Date TEXT NOT NULL,

            Location TEXT NOT NULL,
            Latitude REAL NOT NULL,
            Longitude REAL NOT NULL,

            Month_Name_English TEXT NOT NULL,
            Month_Name_Arabic TEXT NOT NULL,

            Month_Start INTEGER NOT NULL
                CHECK (Month_Start IN (0, 1)),

            Conjunction_Date_Time_UTC TEXT,
            Conjunction_Date_Time_Local TEXT,

            Sunset_Date_Time_Local TEXT,
            Moonset_Date_Time_Local TEXT,

            Moon_Age_Hours REAL,
            Elongation_Degrees REAL,
            Moonset_Lag_Minutes REAL,

            Hilal_Visible INTEGER NOT NULL
                CHECK (Hilal_Visible IN (0, 1)),

            Visibility_Rule TEXT NOT NULL,

            PRIMARY KEY (
                Hijri_Year,
                Hijri_Month,
                Hijri_Day,
                Location
            )
        )
    """)

    conn.commit()


# ============================================================
# Julian Day utilities
# ============================================================

def datetime_to_jd(dt):
    """
    Convert timezone-aware UTC datetime to Julian Day.
    """

    dt_utc = dt.astimezone(timezone.utc)

    hour = (
        dt_utc.hour
        + dt_utc.minute / 60
        + dt_utc.second / 3600
        + dt_utc.microsecond / 3_600_000_000
    )

    return swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        hour,
        swe.GREG_CAL,
    )


def jd_to_datetime(jd):
    """
    Convert Julian Day to UTC datetime.
    """

    year, month, day, hour = swe.revjul(
        jd,
        swe.GREG_CAL,
    )

    hour_int = int(hour)
    minute_float = (hour - hour_int) * 60
    minute = int(minute_float)

    second_float = (minute_float - minute) * 60
    second = int(second_float)

    microsecond = int(
        round((second_float - second) * 1_000_000)
    )

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
        tzinfo=timezone.utc,
    )


# ============================================================
# Sun / Moon positions
# ============================================================

def get_sun_longitude(jd):
    result, _ = swe.calc_ut(
        jd,
        swe.SUN,
        swe.FLG_SWIEPH | swe.FLG_SPEED,
    )
    return result[0] % 360.0


def get_moon_longitude(jd):
    result, _ = swe.calc_ut(
        jd,
        swe.MOON,
        swe.FLG_SWIEPH | swe.FLG_SPEED,
    )
    return result[0] % 360.0


def get_elongation(jd):
    """
    Geocentric angular separation between Moon and Sun.
    """

    sun = get_sun_longitude(jd)
    moon = get_moon_longitude(jd)

    return (moon - sun) % 360.0


# ============================================================
# Find New Moon / conjunction
# ============================================================

def find_next_new_moon(start_jd):

    result = swe.pheno_ut(
        start_jd,
        swe.MOON,
        swe.FLG_SWIEPH,
    )

    # Search forward for the next conjunction using
    # the Sun-Moon longitude difference.
    step = 0.25
    jd = start_jd

    previous = get_elongation(jd)

    # Convert separation to signed value around 0.
    if previous > 180:
        previous -= 360

    for _ in range(200):

        next_jd = jd + step
        current = get_elongation(next_jd)

        if current > 180:
            current -= 360

        if previous <= 0 < current:
            lo = jd
            hi = next_jd

            for _ in range(60):
                mid = (lo + hi) / 2
                value = get_elongation(mid)

                if value > 180:
                    value -= 360

                if value > 0:
                    hi = mid
                else:
                    lo = mid

            return (lo + hi) / 2

        jd = next_jd
        previous = current

    raise RuntimeError("Could not find next New Moon")


# ============================================================
# Local sunset
# ============================================================

def get_sunset(date):

    local_midnight = datetime(
        date.year,
        date.month,
        date.day,
        tzinfo=TIMEZONE,
    )

    jd_ut = datetime_to_jd(
        local_midnight.astimezone(timezone.utc)
    )

    geopos = (
        LONGITUDE,
        LATITUDE,
        0.0,
    )

    result = swe.rise_trans(
        jd_ut,
        swe.SUN,
        swe.CALC_SET,
        geopos,
        0.0,
        0.0,
        swe.FLG_SWIEPH,
    )

    sunset_jd = result[1][0]

    return jd_to_datetime(
        sunset_jd
    ).astimezone(TIMEZONE)


# ============================================================
# Moonset
# ============================================================

def get_moonset(after_jd):

    geopos = (
        LONGITUDE,
        LATITUDE,
        0.0,
    )

    result = swe.rise_trans(
        after_jd,
        swe.MOON,
        swe.CALC_SET,
        geopos,
        0.0,
        0.0,
        swe.FLG_SWIEPH,
    )

    moonset_jd = result[1][0]

    return jd_to_datetime(
        moonset_jd
    ).astimezone(TIMEZONE)


# ============================================================
# Evaluate Hilal
# ============================================================

def evaluate_hilal(sunset):

    sunset_jd = datetime_to_jd(
        sunset.astimezone(timezone.utc)
    )

    # --------------------------------------------------------
    # Find preceding conjunction
    # --------------------------------------------------------

    search_start = sunset_jd - 3.0

    conjunction_jd = find_previous_new_moon(
        search_start
    )

    conjunction = jd_to_datetime(
        conjunction_jd
    )

    # --------------------------------------------------------
    # Moon age
    # --------------------------------------------------------

    age_hours = (
        sunset.astimezone(timezone.utc)
        - conjunction
    ).total_seconds() / 3600.0

    # --------------------------------------------------------
    # Elongation at sunset
    # --------------------------------------------------------

    elongation = get_elongation(
        sunset_jd
    )

    if elongation > 180:
        elongation = 360 - elongation

    # --------------------------------------------------------
    # Moonset
    # --------------------------------------------------------

    moonset = get_moonset(
        sunset_jd
    )

    lag_minutes = (
        moonset - sunset
    ).total_seconds() / 60.0

    # --------------------------------------------------------
    # Hilal visibility criterion
    # --------------------------------------------------------

    visible = (
        age_hours >= MIN_MOON_AGE_HOURS
        and
        elongation >= MIN_ELONGATION_DEGREES
        and
        lag_minutes >= MIN_MOONSET_LAG_MINUTES
    )

    return {
        "conjunction": conjunction,
        "sunset": sunset,
        "moonset": moonset,
        "age_hours": age_hours,
        "elongation": elongation,
        "lag_minutes": lag_minutes,
        "visible": visible,
    }


# ============================================================
# Previous New Moon
# ============================================================

def find_previous_new_moon(start_jd):

    step = 0.25
    jd = start_jd

    previous = get_elongation(jd)

    if previous > 180:
        previous -= 360

    for _ in range(200):

        next_jd = jd - step
        current = get_elongation(next_jd)

        if current > 180:
            current -= 360

        if current >= 0 > previous:

            lo = next_jd
            hi = jd

            for _ in range(60):

                mid = (lo + hi) / 2
                value = get_elongation(mid)

                if value > 180:
                    value -= 360

                if value >= 0:
                    lo = mid
                else:
                    hi = mid

            return (lo + hi) / 2

        jd = next_jd
        previous = current

    raise RuntimeError(
        "Could not find previous New Moon"
    )


# ============================================================
# Find next Islamic month start
# ============================================================

def find_next_month_start(search_date):

    """
    Search sunset-by-sunset.

    The first sunset satisfying the Hilal criterion
    establishes the next Islamic month.

    The Islamic civil date begins at that sunset.
    Therefore the first daytime date of the month
    is the following Gregorian date.
    """

    date = search_date

    for _ in range(5):

        sunset = get_sunset(date)

        result = evaluate_hilal(
            sunset
        )

        print()
        print(
            f"Hilal check: {date.isoformat()}"
        )

        print(
            f"  Sunset       : "
            f"{sunset.isoformat()}"
        )

        print(
            f"  Conjunction  : "
            f"{result['conjunction'].isoformat()}"
        )

        print(
            f"  Moon age     : "
            f"{result['age_hours']:.2f} h"
        )

        print(
            f"  Elongation   : "
            f"{result['elongation']:.2f}°"
        )

        print(
            f"  Moonset      : "
            f"{result['moonset'].isoformat()}"
        )

        print(
            f"  Moonset lag  : "
            f"{result['lag_minutes']:.2f} min"
        )

        print(
            f"  Hilal        : "
            f"{'VISIBLE' if result['visible'] else 'NOT VISIBLE'}"
        )

        if result["visible"]:

            return {
                "date": date + timedelta(days=1),
                "sunset_date": date,
                **result,
            }

        date += timedelta(days=1)

    raise RuntimeError(
        "No Hilal found within 5 days."
    )


# ============================================================
# Populate one Islamic year
# ============================================================

def populate_year(
    conn,
    hijri_year,
    first_month_start,
):

    current_start = first_month_start

    for month in range(1, 13):

        month_name, month_name_arabic = (
            MONTH_NAMES[month]
        )

        # ----------------------------------------------------
        # Find next month
        # ----------------------------------------------------

        next_month = (
            find_next_month_start(
                current_start + timedelta(days=27)
            )
        )

        next_start = next_month["date"]

        # ----------------------------------------------------
        # Number of days
        # ----------------------------------------------------

        month_days = (
            next_start - current_start
        ).days

        if month_days not in (29, 30):

            raise RuntimeError(
                f"Invalid Islamic month length: "
                f"{hijri_year}-{month} = "
                f"{month_days} days"
            )

        # ----------------------------------------------------
        # Recalculate Hilal data for actual month boundary
        # ----------------------------------------------------

        boundary_date = (
            current_start - timedelta(days=1)
        )

        boundary_sunset = get_sunset(
            boundary_date
        )

        boundary = evaluate_hilal(
            boundary_sunset
        )

        # ----------------------------------------------------
        # Insert every day
        # ----------------------------------------------------

        for day in range(
            1,
            month_days + 1
        ):

            gregorian_date = (
                current_start
                + timedelta(days=day - 1)
            )

            month_start = (
                1 if day == 1 else 0
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO Islamic_Calendar (
                    Hijri_Year,
                    Hijri_Month,
                    Hijri_Day,
                    Gregorian_Date,

                    Location,
                    Latitude,
                    Longitude,

                    Month_Name_English,
                    Month_Name_Arabic,

                    Month_Start,

                    Conjunction_Date_Time_UTC,
                    Conjunction_Date_Time_Local,

                    Sunset_Date_Time_Local,
                    Moonset_Date_Time_Local,

                    Moon_Age_Hours,
                    Elongation_Degrees,
                    Moonset_Lag_Minutes,

                    Hilal_Visible,
                    Visibility_Rule
                )
                VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    ?,
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?
                )
                """,
                (
                    hijri_year,
                    month,
                    day,
                    gregorian_date.isoformat(),

                    LOCATION,
                    LATITUDE,
                    LONGITUDE,

                    month_name,
                    month_name_arabic,

                    month_start,

                    boundary["conjunction"]
                        .astimezone(timezone.utc)
                        .isoformat(),

                    boundary["conjunction"]
                        .astimezone(TIMEZONE)
                        .isoformat(),

                    boundary["sunset"].isoformat(),
                    boundary["moonset"].isoformat(),

                    boundary["age_hours"],
                    boundary["elongation"],
                    boundary["lag_minutes"],

                    boundary["visible"],
                    VISIBILITY_RULE,
                ),
            )

        print(
            f"{hijri_year}-{month:02d} "
            f"{month_name}: "
            f"{month_days} days "
            f"{current_start} -> "
            f"{next_start - timedelta(days=1)}"
        )

        current_start = next_start


# ============================================================
# Main
# ============================================================

def main():

    conn = get_connection()

    try:

        create_table(conn)

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # This is the astronomical/Indian seed.
        #
        # 1 Muharram 1448 was reported in parts of India
        # as Wednesday 17 June 2026.
        #
        # ----------------------------------------------------

        first_month_start = datetime(
            2026,
            6,
            17,
            tzinfo=TIMEZONE,
        ).date()

        populate_year(
            conn,
            1448,
            first_month_start,
        )

        conn.commit()

        print()
        print(
            "Islamic_Calendar populated successfully."
        )

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


if __name__ == "__main__":
    main()
