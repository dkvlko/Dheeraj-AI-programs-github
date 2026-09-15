
#!/usr/bin/env python3

from datetime import datetime, date, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import sqlite3

import swisseph as swe


# ============================================================
# Configuration
# ============================================================

DATABASE = Path(
    "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"
)

LOCATION = "Lucknow, Uttar Pradesh, India"
LATITUDE = 26.8467
LONGITUDE = 80.9462
TIMEZONE = ZoneInfo("Asia/Kolkata")

CALENDAR_SYSTEM = "Amanta"

# Current year +/- 2 years
CURRENT_YEAR = datetime.now(TIMEZONE).year
START_YEAR = CURRENT_YEAR - 100
END_YEAR = CURRENT_YEAR + 100


# Swiss Ephemeris
swe.set_sid_mode(swe.SIDM_LAHIRI)

FLAGS = (
    swe.FLG_SWIEPH
    | swe.FLG_SPEED
    | swe.FLG_SIDEREAL
)


# ============================================================
# Astronomical functions
# ============================================================

def sun_moon_longitudes(dt_utc):
    """
    Return geocentric sidereal Sun and Moon longitudes
    for a UTC datetime.
    """

    hour = (
        dt_utc.hour
        + dt_utc.minute / 60.0
        + dt_utc.second / 3600.0
        + dt_utc.microsecond / 3_600_000_000.0
    )

    jd_ut = swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        hour
    )

    sun_result, _ = swe.calc_ut(
        jd_ut,
        swe.SUN,
        FLAGS
    )

    moon_result, _ = swe.calc_ut(
        jd_ut,
        swe.MOON,
        FLAGS
    )

    sun_longitude = sun_result[0] % 360.0
    moon_longitude = moon_result[0] % 360.0

    return sun_longitude, moon_longitude


def angular_separation(dt_utc):
    """
    Moon longitude - Sun longitude modulo 360.
    """

    sun, moon = sun_moon_longitudes(dt_utc)

    return (moon - sun) % 360.0


def tithi_at(dt_utc):
    """
    Return:
        tithi number: 1-15
        paksha: Shukla / Krishna
        angular separation
    """

    separation = angular_separation(dt_utc)

    tithi_30 = int(separation // 12.0) + 1

    if tithi_30 <= 15:
        paksha = "Shukla"
        tithi = tithi_30
    else:
        paksha = "Krishna"
        tithi = tithi_30 - 15

    return tithi, paksha, separation


def is_krishna_chaturdashi(dt_utc):
    """
    Krishna Chaturdashi is angular separation:

        336 <= separation < 348 degrees
    """

    tithi, paksha, separation = tithi_at(dt_utc)

    return (
        paksha == "Krishna"
        and tithi == 14
    )


# ============================================================
# Date/time utilities
# ============================================================

def parse_local_datetime(value):
    """
    Parse ISO datetime stored in SQLite.
    """

    dt = datetime.fromisoformat(value)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)

    return dt


def parse_local_date(value):
    return date.fromisoformat(value)


def local_to_utc(dt_local):
    return dt_local.astimezone(ZoneInfo("UTC"))


# ============================================================
# Nishita Kaal
# ============================================================

def calculate_nishita(sunset_local, sunrise_next_local):
    """
    Calculate Nishita Kaal as the middle one-eighth
    of the local night.

    Night duration is:

        sunset -> next sunrise

    Nishita is centered around the middle of that night.

    One eighth of the night is used on either side
    of the middle point.
    """

    night_duration = (
        sunrise_next_local - sunset_local
    )

    middle = (
        sunset_local
        + night_duration / 2
    )

    eighth = night_duration / 8

    nishita_start = middle - eighth / 2
    nishita_end = middle + eighth / 2

    return nishita_start, nishita_end


# ============================================================
# Database creation
# ============================================================

def create_table(conn):

    conn.execute("""
        DROP TABLE IF EXISTS Maha_Shivratri;
    """)

    conn.execute("""
        CREATE TABLE Maha_Shivratri (

            Date TEXT NOT NULL,

            Date_Time_Start_UTC TEXT NOT NULL,
            Date_Time_End_UTC TEXT NOT NULL,

            Date_Time_Start_Local TEXT NOT NULL,
            Date_Time_End_Local TEXT NOT NULL,

            Location TEXT NOT NULL,

            Latitude REAL NOT NULL,
            Longitude REAL NOT NULL,

            Masa_Number TEXT NOT NULL,
            Masa_English TEXT NOT NULL,
            Masa_Hindi TEXT NOT NULL,

            Masa_Type TEXT NOT NULL,

            Tithi TEXT NOT NULL,
            Paksha TEXT NOT NULL,

            Sunset_Local TEXT NOT NULL,
            Sunrise_Next_Day_Local TEXT NOT NULL,

            Nishita_Start_Local TEXT NOT NULL,
            Nishita_End_Local TEXT NOT NULL,

            PRIMARY KEY (Date, Location)
        );
    """)

    conn.commit()


# ============================================================
# Retrieve Magha Masa intervals
# ============================================================

def get_magha_masas(conn):
    """
    Return Magha Masa intervals from Masa_Transition.

    Masa_Transition does not store latitude/longitude.
    Latitude and longitude are supplied by the program-level
    astronomical configuration.
    """

    rows = conn.execute("""
        SELECT
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
        FROM Masa_Transition
        WHERE Location = ?
          AND Calendar_System = ?
          AND Masa_English = ?
        ORDER BY Start_Date_Time_UTC
    """, (
        LOCATION,
        CALENDAR_SYSTEM,
        "Magha",
    )).fetchall()

    return rows

# ============================================================
# Sunrise / sunset
# ============================================================

def get_sun_position(conn, local_date):

    row = conn.execute("""
        SELECT
            Date,
            Sunrise_Time,
            Sunset_Time
        FROM Sun_Position
        WHERE Date = ?
          AND Location = ?
    """, (
        local_date.isoformat(),
        LOCATION,
    )).fetchone()

    return row


def get_sunset_and_next_sunrise(conn, local_date):

    current = get_sun_position(
        conn,
        local_date
    )

    if current is None:
        raise RuntimeError(
            f"No Sun_Position record for "
            f"{local_date}"
        )

    next_day = local_date + timedelta(days=1)

    following = get_sun_position(
        conn,
        next_day
    )

    if following is None:
        raise RuntimeError(
            f"No Sun_Position record for "
            f"{next_day}"
        )

    sunset_time = time.fromisoformat(
        current[2]
    )

    sunrise_time = time.fromisoformat(
        following[1]
    )

    sunset_local = datetime.combine(
        local_date,
        sunset_time,
        tzinfo=TIMEZONE
    )

    sunrise_next_local = datetime.combine(
        next_day,
        sunrise_time,
        tzinfo=TIMEZONE
    )

    return (
        sunset_local,
        sunrise_next_local
    )


# ============================================================
# Find Maha Shivratri
# ============================================================

def find_maha_shivratri(conn, magha_rows):

    results = []

    for row in magha_rows:

        (
            masa_start_utc,
            masa_end_utc,
            masa_start_local,
            masa_end_local,
            location,
            calendar_system,
            masa_number,
            masa_english,
            masa_hindi,
            masa_type,
        ) = row

        latitude = LATITUDE
        longitude = LONGITUDE

        start_local = parse_local_datetime(
            masa_start_local
        )

        end_local = parse_local_datetime(
            masa_end_local
        )

        # Restrict the search to the requested
        # Gregorian years.
        search_start = max(
            start_local,
            datetime(
                START_YEAR,
                1,
                1,
                tzinfo=TIMEZONE
            )
        )

        search_end = min(
            end_local,
            datetime(
                END_YEAR + 1,
                1,
                1,
                tzinfo=TIMEZONE
            )
        )

        current_date = search_start.date()

        while current_date <= search_end.date():

            # We need the night beginning on this
            # Gregorian date.
            try:
                sunset_local, sunrise_next_local = (
                    get_sunset_and_next_sunrise(
                        conn,
                        current_date
                    )
                )

            except RuntimeError:
                current_date += timedelta(days=1)
                continue

            # Check that this night belongs to
            # the Magha Masa interval.
            if not (
                sunset_local >= start_local
                and sunset_local < end_local
            ):
                current_date += timedelta(days=1)
                continue

            # Calculate Nishita Kaal.
            nishita_start, nishita_end = (
                calculate_nishita(
                    sunset_local,
                    sunrise_next_local
                )
            )

            # Check the middle of Nishita.
            nishita_middle = (
                nishita_start
                + (
                    nishita_end
                    - nishita_start
                ) / 2
            )

            nishita_middle_utc = (
                local_to_utc(
                    nishita_middle
                )
            )

            (
                tithi,
                paksha,
                separation
            ) = tithi_at(
                nishita_middle_utc
            )

            if (
                paksha == "Krishna"
                and tithi == 14
            ):

                # Find approximate beginning/end of
                # Chaturdashi around this date.
                #
                # Search backwards and forwards
                # in 30-minute steps.
                start_utc = find_tithi_boundary(
                    nishita_middle_utc,
                    direction=-1,
                    target_start=336.0
                )

                end_utc = find_tithi_boundary(
                    nishita_middle_utc,
                    direction=1,
                    target_start=348.0
                )

                start_local = (
                    start_utc.astimezone(
                        TIMEZONE
                    )
                )

                end_local = (
                    end_utc.astimezone(
                        TIMEZONE
                    )
                )

                results.append((
                    current_date.isoformat(),

                    start_utc.isoformat(),
                    end_utc.isoformat(),

                    start_local.isoformat(),
                    end_local.isoformat(),

                    location,

                    latitude,
                    longitude,

                    masa_number,
                    masa_english,
                    masa_hindi,

                    masa_type,

                    "14",
                    "Krishna",

                    sunset_local.isoformat(),
                    sunrise_next_local.isoformat(),

                    nishita_start.isoformat(),
                    nishita_end.isoformat(),
                ))

                # There should only be one Maha
                # Shivratri in a Magha Masa.
                break

            current_date += timedelta(days=1)

    return results


# ============================================================
# Find exact-ish Tithi boundary
# ============================================================

def find_tithi_boundary(
    center_utc,
    direction,
    target_start
):
    """
    Find the Tithi boundary around center_utc.

    target_start:
        336° = beginning of Krishna Chaturdashi
        348° = beginning of Amavasya

    Uses a coarse search followed by binary
    refinement.

    direction:
        -1 = search backwards
        +1 = search forwards
    """

    step = timedelta(minutes=30)

    current = center_utc

    # Search until we bracket the boundary.
    for _ in range(100):

        previous = current

        current = current + (
            step * direction
        )

        previous_angle = angular_separation(
            previous
        )

        current_angle = angular_separation(
            current
        )

        if target_start == 336.0:

            # Krishna Chaturdashi starts when
            # separation crosses 336° upward.
            crossed = (
                direction == -1
                and previous_angle >= 336.0
                and current_angle < 336.0
            ) or (
                direction == 1
                and previous_angle < 336.0
                and current_angle >= 336.0
            )

        else:

            # Amavasya starts when separation
            # crosses 348° upward.
            crossed = (
                direction == -1
                and previous_angle >= 348.0
                and current_angle < 348.0
            ) or (
                direction == 1
                and previous_angle < 348.0
                and current_angle >= 348.0
            )

        # Handle 360 -> 0 wrapping.
        if target_start in (336.0, 348.0):

            if (
                previous_angle > 300.0
                and current_angle < 60.0
            ):
                if target_start == 348.0:
                    crossed = True

        if crossed:
            low = min(previous, current)
            high = max(previous, current)

            # Binary search to approximately 1 second.
            while (
                high - low
            ) > timedelta(seconds=1):

                middle = (
                    low
                    + (high - low) / 2
                )

                angle = angular_separation(
                    middle
                )

                if target_start == 348.0:

                    if angle >= 348.0:
                        low = middle
                    else:
                        high = middle

                else:

                    if angle < target_start:
                        low = middle
                    else:
                        high = middle

            return high

    raise RuntimeError(
        f"Unable to find Tithi boundary "
        f"{target_start}° around "
        f"{center_utc}"
    )


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("Maha Shivratri generator")
    print("------------------------")
    print(f"Database   : {DATABASE}")
    print(f"Location   : {LOCATION}")
    print(f"Calendar   : {CALENDAR_SYSTEM}")
    print(
        f"Year range : "
        f"{START_YEAR} - {END_YEAR}"
    )
    print()

    with sqlite3.connect(DATABASE) as conn:

        create_table(conn)

        magha_rows = get_magha_masas(conn)

        print(
            f"Magha Masa records found: "
            f"{len(magha_rows)}"
        )

        results = find_maha_shivratri(
            conn,
            magha_rows
        )

        insert_sql = """
            INSERT INTO Maha_Shivratri (
                Date,

                Date_Time_Start_UTC,
                Date_Time_End_UTC,

                Date_Time_Start_Local,
                Date_Time_End_Local,

                Location,

                Latitude,
                Longitude,

                Masa_Number,
                Masa_English,
                Masa_Hindi,

                Masa_Type,

                Tithi,
                Paksha,

                Sunset_Local,
                Sunrise_Next_Day_Local,

                Nishita_Start_Local,
                Nishita_End_Local
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?
            );
        """

        conn.executemany(
            insert_sql,
            results
        )

        conn.commit()

        print()
        print(
            f"Maha Shivratri records inserted: "
            f"{len(results)}"
        )

        print()

        for result in results:
            print(
                f"{result[0]}  "
                f"{result[9]} {result[10]}  "
                f"{result[12]} {result[13]}"
            )


if __name__ == "__main__":
    main()
