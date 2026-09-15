
#!/usr/bin/env python3

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import sunrise, sunset

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Float,
    PrimaryKeyConstraint,
)

from sqlalchemy.orm import DeclarativeBase, Session


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
END_DATE = date(2126, 1, 1)


# ============================================================
# SQLAlchemy Base
# ============================================================

class Base(DeclarativeBase):
    pass


# ============================================================
# Sun_Position table
# ============================================================

class SunPosition(Base):

    __tablename__ = "Sun_Position"

    Date = Column(
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

    Sunrise_Time = Column(
        String,
        nullable=False,
    )

    Sunset_Time = Column(
        String,
        nullable=False,
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "Date",
            "Location",
        ),
    )


# ============================================================
# Database engine
# ============================================================

engine = create_engine(
    DATABASE_URL,
    echo=False,
)


# ============================================================
# Create table if it doesn't exist
# ============================================================

Base.metadata.create_all(engine)


# ============================================================
# Astral observer
# ============================================================

observer = Observer(
    latitude=LATITUDE,
    longitude=LONGITUDE,
)


# ============================================================
# Statistics
# ============================================================

successful = 0
approximated = 0
failed = 0


# ============================================================
# Get previous day's Sun_Position
# ============================================================

def get_previous_day_data(
    session: Session,
    current_date: date,
):
    """
    Return the previous day's sunrise and sunset.

    Returns:
        (sunrise_time, sunset_time)

    or:
        None

    if the previous day's record does not exist.
    """

    previous_date = (
        current_date - timedelta(days=1)
    )

    previous_date_string = (
        previous_date.isoformat()
    )

    row = session.get(
        SunPosition,
        (
            previous_date_string,
            LOCATION,
        ),
    )

    if row is None:
        return None

    return (
        row.Sunrise_Time,
        row.Sunset_Time,
    )


# ============================================================
# Main population
# ============================================================

current_date = START_DATE


with Session(engine) as session:

    while current_date <= END_DATE:

        date_string = current_date.isoformat()

        # ----------------------------------------------------
        # First try normal Astral calculation.
        # ----------------------------------------------------

        try:

            sunrise_dt = sunrise(
                observer,
                date=current_date,
                tzinfo=TIMEZONE,
            )

            sunset_dt = sunset(
                observer,
                date=current_date,
                tzinfo=TIMEZONE,
            )

            sunrise_time = (
                sunrise_dt.strftime("%H:%M:%S")
            )

            sunset_time = (
                sunset_dt.strftime("%H:%M:%S")
            )

            # ------------------------------------------------
            # Insert or update normal record.
            # ------------------------------------------------

            row = session.get(
                SunPosition,
                (
                    date_string,
                    LOCATION,
                ),
            )

            if row is None:

                row = SunPosition(
                    Date=date_string,
                    Location=LOCATION,
                    Latitude=LATITUDE,
                    Longitude=LONGITUDE,
                    Sunrise_Time=sunrise_time,
                    Sunset_Time=sunset_time,
                )

                session.add(row)

            else:

                row.Latitude = LATITUDE
                row.Longitude = LONGITUDE
                row.Sunrise_Time = sunrise_time
                row.Sunset_Time = sunset_time

            successful += 1

            print(
                f"{current_date}  "
                f"Sunrise: {sunrise_time}  "
                f"Sunset: {sunset_time}"
            )

        # ----------------------------------------------------
        # Astral failed.
        # ----------------------------------------------------

        except Exception as e:

            print(
                f"{current_date}  "
                f"ASTRAL ERROR: {e}"
            )

            # ------------------------------------------------
            # Try previous day's data.
            # ------------------------------------------------

            try:

                previous_data = (
                    get_previous_day_data(
                        session,
                        current_date,
                    )
                )

                if previous_data is None:

                    failed += 1

                    print(
                        f"{current_date}  "
                        f"ERROR: Previous day's "
                        f"Sun_Position record does not exist."
                    )

                else:

                    (
                        sunrise_time,
                        sunset_time,
                    ) = previous_data

                    # ----------------------------------------
                    # Insert or update approximate record.
                    # ----------------------------------------

                    row = session.get(
                        SunPosition,
                        (
                            date_string,
                            LOCATION,
                        ),
                    )

                    if row is None:

                        row = SunPosition(
                            Date=date_string,
                            Location=LOCATION,
                            Latitude=LATITUDE,
                            Longitude=LONGITUDE,
                            Sunrise_Time=sunrise_time,
                            Sunset_Time=sunset_time,
                        )

                        session.add(row)

                    else:

                        row.Latitude = LATITUDE
                        row.Longitude = LONGITUDE
                        row.Sunrise_Time = sunrise_time
                        row.Sunset_Time = sunset_time

                    approximated += 1

                    print(
                        f"{current_date}  "
                        f"APPROX: "
                        f"Sunrise: {sunrise_time}  "
                        f"Sunset: {sunset_time}  "
                        f"(copied from "
                        f"{current_date - timedelta(days=1)})"
                    )

            except Exception as fallback_error:

                failed += 1

                print(
                    f"{current_date}  "
                    f"FALLBACK ERROR: "
                    f"{fallback_error}"
                )

        # ----------------------------------------------------
        # Move to next date.
        # ----------------------------------------------------

        current_date += timedelta(days=1)

        # ----------------------------------------------------
        # Periodic commit.
        # ----------------------------------------------------

        total_processed = (
            successful
            + approximated
            + failed
        )

        if total_processed % 1000 == 0:

            session.commit()

            print(
                f"--- Committed after "
                f"{total_processed} dates ---"
            )


    # ========================================================
    # Final commit
    # ========================================================

    session.commit()


# ============================================================
# Final report
# ============================================================

print()
print("=" * 70)
print("Sun_Position population completed.")
print("=" * 70)
print(f"Successfully calculated : {successful}")
print(f"Approximate records     : {approximated}")
print(f"Failed                  : {failed}")
print(
    f"Total processed         : "
    f"{successful + approximated + failed}"
)
print("=" * 70)
