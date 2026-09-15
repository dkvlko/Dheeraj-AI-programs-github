from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import swisseph as swe

from sqlalchemy import (
    create_engine,
    text,
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
# DATE / TIME RANGE
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

engine = create_engine(
    DATABASE_URL,
    echo=False,
)


# ============================================================
# TITHI
# ============================================================

def calculate_tithi(
    sun_longitude: float,
    moon_longitude: float,
):
    """
    Calculate:

        Angular separation
        Tithi
        Paksha

    from geocentric sidereal Sun and Moon
    longitudes.
    """

    angular_separation = (
        moon_longitude - sun_longitude
    ) % 360.0

    # 12 degrees per tithi
    tithi_number_30 = (
        int(angular_separation // 12.0)
        + 1
    )

    if tithi_number_30 <= 15:

        paksha = "Shukla"

        tithi = f"{tithi_number_30:02d}"

    else:

        paksha = "Krishna"

        tithi = (
            f"{tithi_number_30 - 15:02d}"
        )

    return (
        angular_separation,
        tithi,
        paksha,
    )


# ============================================================
# SUN / MOON LONGITUDES
# ============================================================

def get_sun_moon_longitudes(
    dt_utc: datetime,
):
    """
    Calculate geocentric sidereal Sun and Moon
    longitudes using Swiss Ephemeris.
    """

    dt_utc = dt_utc.astimezone(
        timezone.utc
    )

    # --------------------------------------------------------
    # Julian Day
    # --------------------------------------------------------

    hour_utc = (
        dt_utc.hour
        + dt_utc.minute / 60.0
        + dt_utc.second / 3600.0
        + dt_utc.microsecond / 3_600_000_000.0
    )

    jd_ut = swe.julday(
        dt_utc.year,
        dt_utc.month,
        dt_utc.day,
        hour_utc,
    )

    # --------------------------------------------------------
    # Sun
    # --------------------------------------------------------

    sun_position, _ = swe.calc_ut(
        jd_ut,
        swe.SUN,
        FLAGS,
    )

    # --------------------------------------------------------
    # Moon
    # --------------------------------------------------------

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
# MAIN
# ============================================================

def populate_sun_moon_position():

    print()
    print("=" * 70)
    print("Populating Sun_Moon_Position")
    print("=" * 70)

    print(
        "Start UTC:",
        START_DATE.isoformat(),
    )

    print(
        "End UTC  :",
        END_DATE.isoformat(),
    )

    print(
        "Location :",
        LOCATION,
    )

    print()

    # --------------------------------------------------------
    # SQL
    # --------------------------------------------------------

    insert_sql = text(
        """
        INSERT OR REPLACE INTO Sun_Moon_Position
        (
            Date_Time_UTC,
            Date_Time_Local,
            Location,
            Latitude,
            Longitude,
            Sun_Longitude,
            Moon_Longitude,
            Angular_Separation,
            Tithi,
            Paksha
        )
        VALUES
        (
            :date_time_utc,
            :date_time_local,
            :location,
            :latitude,
            :longitude,
            :sun_longitude,
            :moon_longitude,
            :angular_separation,
            :tithi,
            :paksha
        )
        """
    )

    # --------------------------------------------------------
    # Process in batches
    # --------------------------------------------------------

    BATCH_SIZE = 1000

    rows = []

    current_utc = START_DATE

    total_rows = 0

    with engine.begin() as connection:

        while current_utc < END_DATE:

            for hour in range(0, 24, 3):

                observation_utc = current_utc.replace(
                    hour=hour,
                    minute=0,
                    second=0,
                    microsecond=0,
                )

                # ------------------------------------------------
                # Sun / Moon
                # ------------------------------------------------

                (
                    sun_longitude,
                    moon_longitude,
                ) = get_sun_moon_longitudes(
                    observation_utc
                )

                # ------------------------------------------------
                # Tithi
                # ------------------------------------------------

                (
                    angular_separation,
                    tithi,
                    paksha,
                ) = calculate_tithi(
                    sun_longitude,
                    moon_longitude,
                )

                # ------------------------------------------------
                # Local time
                # ------------------------------------------------

                observation_local = (
                    observation_utc.astimezone(
                        TIMEZONE
                    )
                )

                # ------------------------------------------------
                # Row
                # ------------------------------------------------

                rows.append(
                    {
                        "date_time_utc":
                            observation_utc.isoformat(),

                        "date_time_local":
                            observation_local.isoformat(),

                        "location":
                            LOCATION,

                        "latitude":
                            LATITUDE,

                        "longitude":
                            LONGITUDE,

                        "sun_longitude":
                            sun_longitude,

                        "moon_longitude":
                            moon_longitude,

                        "angular_separation":
                            angular_separation,

                        "tithi":
                            tithi,

                        "paksha":
                            paksha,
                    }
                )

                # ------------------------------------------------
                # Bulk insert
                # ------------------------------------------------

                if len(rows) >= BATCH_SIZE:

                    connection.execute(
                        insert_sql,
                        rows,
                    )

                    total_rows += len(rows)

                    print(
                        f"Inserted {total_rows:,} rows "
                        f"through "
                        f"{observation_utc.isoformat()}"
                    )

                    rows.clear()

            current_utc += timedelta(days=1)

        # --------------------------------------------------------
        # Remaining rows
        # --------------------------------------------------------

        if rows:

            connection.execute(
                insert_sql,
                rows,
            )

            total_rows += len(rows)

            rows.clear()

    print()
    print("=" * 70)

    print(
        f"Total rows inserted/updated: "
        f"{total_rows:,}"
    )

    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    populate_sun_moon_position()

    print()
    print(
        "Sun_Moon_Position populated successfully."
    )
