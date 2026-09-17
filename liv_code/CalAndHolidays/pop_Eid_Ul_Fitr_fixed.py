import sqlite3
import math
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

START_HIJRI_YEAR = 1345       # 1927 CE
END_HIJRI_YEAR = 1549         # 2125 CE


# Swiss Ephemeris
swe.set_ephe_path("")


# ============================================================
# DATABASE
# ============================================================

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS Eid_Ul_Fitr (
    Hijri_Year TEXT NOT NULL,
    Date TEXT NOT NULL,
    Location TEXT NOT NULL,
    Ramadan_Anchor_Date TEXT NOT NULL,
    New_Moon_Local TEXT NOT NULL,
    Observation_Date_Local TEXT NOT NULL,
    Sunset_Time_Local TEXT NOT NULL,
    Moon_Age_Hours REAL NOT NULL,
    Moon_Sun_Elongation_Degrees REAL NOT NULL,
    Moon_Altitude_At_Sunset_Degrees REAL NOT NULL,
    Moon_Azimuth_At_Sunset_Degrees REAL NOT NULL,
    Sun_Altitude_At_Sunset_Degrees REAL NOT NULL,
    Sun_Azimuth_At_Sunset_Degrees REAL NOT NULL,
    Azimuth_Difference_Degrees REAL NOT NULL,
    Arc_of_Vision_Degrees REAL NOT NULL,
    Moonset_After_Sunset_Minutes REAL NOT NULL,
    Visibility_Status TEXT NOT NULL,
    Rule_Applied TEXT NOT NULL,
    PRIMARY KEY (Hijri_Year, Location)
)
"""


# ============================================================
# DATE / TIME HELPERS
# ============================================================

def datetime_to_jd(dt):
    """
    Convert timezone-aware datetime to Julian Day (UT).
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
        swe.GREG_CAL
    )


def jd_to_datetime_utc(jd):
    """
    Convert Julian Day to UTC datetime.
    """
    year, month, day, hour = swe.revjul(jd, swe.GREG_CAL)

    hour_int = int(hour)
    minute_float = (hour - hour_int) * 60.0
    minute_int = int(minute_float)

    second_float = (minute_float - minute_int) * 60.0
    second_int = int(second_float)

    microsecond = int(round(
        (second_float - second_int) * 1_000_000
    ))

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
        tzinfo=timezone.utc
    )


def jd_to_local(jd):
    return jd_to_datetime_utc(jd).astimezone(TIMEZONE)


def format_local(dt):
    return dt.astimezone(TIMEZONE).isoformat()


# ============================================================
# SWISS EPHEMERIS POSITION FUNCTIONS
# ============================================================

def moon_sun_longitudes(jd):
    """
    Return geocentric ecliptic longitudes of Moon and Sun.
    """

    sun, _ = swe.calc_ut(
        jd,
        swe.SUN,
        swe.FLG_SWIEPH
    )

    moon, _ = swe.calc_ut(
        jd,
        swe.MOON,
        swe.FLG_SWIEPH
    )

    return moon[0], sun[0]


def find_new_moon_near(date_dt):
    """
    Find the exact astronomical New Moon near a supplied date.

    New Moon = geocentric ecliptic longitude Moon == Sun.
    """

    center_jd = datetime_to_jd(date_dt)

    # Search ±2 days.
    start_jd = center_jd - 2.0
    end_jd = center_jd + 2.0

    def angle_difference(jd):
        moon_lon, sun_lon = moon_sun_longitudes(jd)

        diff = moon_lon - sun_lon

        while diff > 180.0:
            diff -= 360.0

        while diff < -180.0:
            diff += 360.0

        return diff

    step = 0.05

    previous_jd = start_jd
    previous_value = angle_difference(previous_jd)

    jd = start_jd + step

    while jd <= end_jd:

        current_value = angle_difference(jd)

        # Normal zero crossing.
        if previous_value <= 0.0 < current_value:
            return binary_search_new_moon(
                previous_jd,
                jd
            )

        if previous_value >= 0.0 > current_value:
            return binary_search_new_moon(
                previous_jd,
                jd
            )

        previous_jd = jd
        previous_value = current_value

        jd += step

    raise RuntimeError(
        f"Could not find New Moon near {date_dt}"
    )


def binary_search_new_moon(jd1, jd2):
    """
    Refine the Moon-Sun longitude crossing.
    """

    def angle_difference(jd):
        moon_lon, sun_lon = moon_sun_longitudes(jd)

        diff = moon_lon - sun_lon

        while diff > 180.0:
            diff -= 360.0

        while diff < -180.0:
            diff += 360.0

        return diff

    f1 = angle_difference(jd1)

    for _ in range(60):

        mid = (jd1 + jd2) / 2.0
        fm = angle_difference(mid)

        if abs(fm) < 1e-10:
            return mid

        if (f1 <= 0.0 <= fm) or (f1 >= 0.0 >= fm):
            jd2 = mid
        else:
            jd1 = mid
            f1 = fm

    return (jd1 + jd2) / 2.0


# ============================================================
# SUNRISE / SUNSET
# ============================================================

def sun_event(date_obj, event):
    """
    Calculate sunrise or sunset for Lucknow.

    event:
        "rise"
        "set"
    """

    jd_start = swe.julday(
        date_obj.year,
        date_obj.month,
        date_obj.day,
        0.0,
        swe.GREG_CAL
    )

    geopos = (
        LONGITUDE,
        LATITUDE,
        0.0
    )

    if event == "rise":
        rsmi = swe.CALC_RISE
    elif event == "set":
        rsmi = swe.CALC_SET
    else:
        raise ValueError(event)

    result, tret = swe.rise_trans(
        jd_start,
        swe.SUN,
        rsmi,
        geopos,
        0.0,
        0.0,
        swe.FLG_SWIEPH
    )

    if result != 0:
        raise RuntimeError(
            f"Swiss Ephemeris failed to calculate Sun {event}"
        )

    return jd_to_local(tret[0])


# ============================================================
# MOON POSITION
# ============================================================

def moon_position_at(jd):
    """
    Topocentric Moon altitude and azimuth.
    """

    swe.set_topo(
        LONGITUDE,
        LATITUDE,
        0.0
    )

    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_TOPOCTR
    )

    moon, _ = swe.calc_ut(
        jd,
        swe.MOON,
        flags
    )

    # Swiss Ephemeris azimuth convention:
    # azimuth measured westward from south in some APIs,
    # so we use the explicit azimuth calculation below.
    lon = moon[0]
    lat = moon[1]
    distance = moon[2]

    return lon, lat, distance


def apparent_alt_az(body, jd):
    """
    Return topocentric apparent altitude and azimuth.

    Swiss Ephemeris azimuth:
        0 = South
        90 = West
        180 = North
        270 = East
    """

    swe.set_topo(
        LONGITUDE,
        LATITUDE,
        0.0
    )

    flags = (
        swe.FLG_SWIEPH
        | swe.FLG_EQUATORIAL
        | swe.FLG_TOPOCTR
    )

    xx, _ = swe.calc_ut(
        jd,
        body,
        flags
    )

    ra = xx[0]
    decl = xx[1]

    # Swiss Ephemeris returns Greenwich sidereal time.
    # Add Lucknow's longitude to obtain local sidereal time.
    local_sidereal_degrees = (
        swe.sidtime(jd) * 15.0
        + LONGITUDE
    ) % 360.0

    # Convert RA to local hour angle in degrees.
    hour_angle = local_sidereal_degrees - ra

    hour_angle = math.radians(hour_angle)
    decl_rad = math.radians(decl)
    lat_rad = math.radians(LATITUDE)

    altitude = math.asin(
        math.sin(lat_rad) * math.sin(decl_rad)
        + math.cos(lat_rad)
        * math.cos(decl_rad)
        * math.cos(hour_angle)
    )

    altitude_deg = math.degrees(altitude)

    # Azimuth measured clockwise from North.
    y = math.sin(hour_angle)

    x = (
        math.cos(hour_angle) * math.sin(lat_rad)
        - math.tan(decl_rad) * math.cos(lat_rad)
    )

    azimuth_deg = math.degrees(
        math.atan2(y, x)
    )

    azimuth_deg = (azimuth_deg + 180.0) % 360.0

    return altitude_deg, azimuth_deg


# ============================================================
# MOONSET
# ============================================================

def moonset_after_sunset(date_obj, sunset):
    """
    Find Moonset after the given sunset.
    """

    jd_start = datetime_to_jd(sunset)

    geopos = (
        LONGITUDE,
        LATITUDE,
        0.0
    )

    result, tret = swe.rise_trans(
        jd_start,
        swe.MOON,
        swe.CALC_SET,
        geopos,
        0.0,
        0.0,
        swe.FLG_SWIEPH
    )

    if result != 0:
        return None

    moonset = jd_to_local(tret[0])

    if moonset <= sunset:
        return None

    return moonset


# ============================================================
# ANGLE HELPERS
# ============================================================

def angular_difference(a, b):
    """
    Smallest absolute difference between two angles.
    """

    diff = abs(a - b)

    if diff > 180.0:
        diff = 360.0 - diff

    return diff


# ============================================================
# VISIBILITY CLASSIFICATION
# ============================================================

def classify_visibility(
    moon_age_hours,
    elongation,
    moon_altitude,
    moonset_after_sunset_minutes
):
    """
    Practical approximate classification.

    IMPORTANT:
    This is an astronomical approximation, not a religious
    sighting guarantee.
    """

    if (
        moon_age_hours >= 20.0
        and elongation >= 10.0
        and moon_altitude >= 5.0
        and moonset_after_sunset_minutes >= 30.0
    ):
        return "LIKELY"

    if (
        moon_age_hours >= 16.0
        and elongation >= 8.0
        and moon_altitude >= 3.0
        and moonset_after_sunset_minutes >= 20.0
    ):
        return "POSSIBLE"

    return "UNLIKELY"


# ============================================================
# FIND RAMADAN-ENDING NEW MOON
# ============================================================

def find_ramadan_ending_new_moon(ramadan_end_date):
    """
    Find the astronomical New Moon associated with the end of
    the Ramadan interval supplied by the Ramadan table.

    Ramadan_End_Date identifies the correct Ramadan cycle.
    The conjunction ending Ramadan is searched for around that
    date rather than being derived from a fixed 29/30-day offset.
    """

    target = datetime.combine(
        ramadan_end_date,
        datetime.min.time()
    ).replace(tzinfo=TIMEZONE)

    return find_new_moon_near(target)


# ============================================================
# PROCESS ONE RAMADAN YEAR
# ============================================================

def process_ramadan_row(row, conn):

    hijri_year = row["Hijri_Year"]

    anchor_date = datetime.strptime(
        row["Ramadan_Start_Date"],
        "%Y-%m-%d"
    ).date()

    ramadan_end_date = datetime.strptime(
        row["Ramadan_End_Date"],
        "%Y-%m-%d"
    ).date()

    ramadan_days = int(row["Ramadan_Days"])

    print(
        f"\nProcessing Hijri {hijri_year} "
        f"(Ramadan {anchor_date} to {ramadan_end_date}, "
        f"{ramadan_days} days)"
    )

    # --------------------------------------------------------
    # Find astronomical New Moon ending Ramadan
    # --------------------------------------------------------

    new_moon_jd = find_ramadan_ending_new_moon(
        ramadan_end_date
    )

    new_moon_local = jd_to_local(new_moon_jd)

    print(
        "  New Moon:",
        format_local(new_moon_local)
    )

    # --------------------------------------------------------
    # First sunset on/after conjunction
    # --------------------------------------------------------

    candidate_dates = [
        new_moon_local.date(),
        new_moon_local.date() + timedelta(days=1)
    ]

    observations = []

    for observation_date in candidate_dates:

        sunset = sun_event(
            observation_date,
            "set"
        )

        # We want the first sunset after conjunction.
        if sunset <= new_moon_local:
            continue

        sunset_jd = datetime_to_jd(sunset)

        # ----------------------------------------------------
        # Moon position at sunset
        # ----------------------------------------------------

        moon_altitude, moon_azimuth = apparent_alt_az(
            swe.MOON,
            sunset_jd
        )

        sun_altitude, sun_azimuth = apparent_alt_az(
            swe.SUN,
            sunset_jd
        )

        azimuth_difference = angular_difference(
            moon_azimuth,
            sun_azimuth
        )

        # Geocentric elongation.
        moon_lon, sun_lon = moon_sun_longitudes(
            sunset_jd
        )

        elongation = angular_difference(
            moon_lon,
            sun_lon
        )

        # Moon age.
        moon_age_hours = (
            sunset_jd - new_moon_jd
        ) * 24.0

        # ----------------------------------------------------
        # Moonset
        # ----------------------------------------------------

        moonset = moonset_after_sunset(
            observation_date,
            sunset
        )

        if moonset is None:
            moonset_after_minutes = 0.0
        else:
            moonset_after_minutes = (
                moonset - sunset
            ).total_seconds() / 60.0

        # ----------------------------------------------------
        # Arc of Vision
        #
        # Here we use Moon altitude as a practical
        # local proxy for the vertical separation.
        # ----------------------------------------------------

        arc_of_vision = moon_altitude

        visibility = classify_visibility(
            moon_age_hours,
            elongation,
            moon_altitude,
            moonset_after_minutes
        )

        observations.append({
            "date": observation_date,
            "sunset": sunset,
            "moon_age": moon_age_hours,
            "elongation": elongation,
            "moon_altitude": moon_altitude,
            "moon_azimuth": moon_azimuth,
            "sun_altitude": sun_altitude,
            "sun_azimuth": sun_azimuth,
            "azimuth_difference": azimuth_difference,
            "arc_of_vision": arc_of_vision,
            "moonset_after_minutes": moonset_after_minutes,
            "visibility": visibility,
        })

        print(
            f"  Observation {observation_date}: "
            f"{visibility} | "
            f"age={moon_age_hours:.2f}h | "
            f"elongation={elongation:.2f}° | "
            f"alt={moon_altitude:.2f}° | "
            f"moonset={moonset_after_minutes:.1f}m"
        )

        # First sunset after conjunction is normally the
        # important observation.
        break

    if not observations:
        raise RuntimeError(
            f"No valid crescent observation found "
            f"for Hijri {hijri_year}"
        )

    observation = observations[0]

    # --------------------------------------------------------
    # Determine Eid date
    # --------------------------------------------------------

    if observation["visibility"] in (
        "LIKELY",
        "POSSIBLE"
    ):
        eid_date = (
            observation["date"]
            + timedelta(days=1)
        )

        rule = (
            "Astronomical crescent visibility at the first "
            "sunset after Ramadan-ending New Moon; "
            "Eid assigned to the following civil date."
        )

    else:
        # Crescent not reasonably visible.
        #
        # Preserve the 29/30-day Ramadan length supplied by
        # the Ramadan table when the crescent is not reasonably
        # visible.
        eid_date = (
            anchor_date
            + timedelta(days=ramadan_days)
        )

        rule = (
            "Crescent not reasonably visible at the first "
            "post-conjunction sunset; Ramadan completed "
            f"{ramadan_days} days according to the Ramadan table."
        )

    # --------------------------------------------------------
    # Store result
    # --------------------------------------------------------

    conn.execute(
        """
        INSERT OR REPLACE INTO Eid_Ul_Fitr (
            Hijri_Year,
            Date,
            Location,
            Ramadan_Anchor_Date,
            New_Moon_Local,
            Observation_Date_Local,
            Sunset_Time_Local,
            Moon_Age_Hours,
            Moon_Sun_Elongation_Degrees,
            Moon_Altitude_At_Sunset_Degrees,
            Moon_Azimuth_At_Sunset_Degrees,
            Sun_Altitude_At_Sunset_Degrees,
            Sun_Azimuth_At_Sunset_Degrees,
            Azimuth_Difference_Degrees,
            Arc_of_Vision_Degrees,
            Moonset_After_Sunset_Minutes,
            Visibility_Status,
            Rule_Applied
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            hijri_year,
            eid_date.isoformat(),
            LOCATION,
            anchor_date.isoformat(),
            format_local(new_moon_local),
            observation["date"].isoformat(),
            format_local(observation["sunset"]),
            observation["moon_age"],
            observation["elongation"],
            observation["moon_altitude"],
            observation["moon_azimuth"],
            observation["sun_altitude"],
            observation["sun_azimuth"],
            observation["azimuth_difference"],
            observation["arc_of_vision"],
            observation["moonset_after_minutes"],
            observation["visibility"],
            rule,
        )
    )

    conn.commit()

    print(
        f"  ==> Eid-ul-Fitr: {eid_date}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    conn.execute(CREATE_TABLE_SQL)
    conn.commit()

    rows = conn.execute(
        """
        SELECT
            Hijri_Year,
            Gregorian_Year,
            Ramadan_Start_Date,
            Ramadan_End_Date,
            Shawwal_Start_Date,
            Tabular_Eid_Ul_Fitr_Date,
            Ramadan_Days,
            Calendar_System,
            Anchor_Type
        FROM Ramadan
        WHERE CAST(Hijri_Year AS INTEGER)
              BETWEEN ? AND ?
        ORDER BY CAST(Hijri_Year AS INTEGER)
        """,
        (
            START_HIJRI_YEAR,
            END_HIJRI_YEAR
        )
    ).fetchall()

    if not rows:
        raise RuntimeError(
            "No Ramadan rows found."
        )

    print(
        f"Found {len(rows)} Ramadan rows."
    )

    for row in rows:

        try:
            process_ramadan_row(
                row,
                conn
            )

        except Exception as exc:

            print(
                f"ERROR processing Hijri "
                f"{row['Hijri_Year']}: {exc}"
            )

    conn.close()

    print("\nFinished.")


if __name__ == "__main__":
    main()
