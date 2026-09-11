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


DATABASE_URL = (
    "sqlite:////data/BLOBS/CalAndHolidays/CalAndHolidays.db"
)

LOCATION = "Lucknow, Uttar Pradesh, India"

LATITUDE = 26.8467
LONGITUDE = 80.9462

TIMEZONE = ZoneInfo("Asia/Kolkata")

START_DATE = date(1926, 1, 1)
END_DATE = date(2126, 1, 1)


class Base(DeclarativeBase):
    pass


class SunPosition(Base):
    __tablename__ = "Sun_Position"

    Date = Column(String, nullable=False)
    Location = Column(String, nullable=False)
    Latitude = Column(Float, nullable=False)
    Longitude = Column(Float, nullable=False)
    Sunrise_Time = Column(String, nullable=False)
    Sunset_Time = Column(String, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("Date", "Location"),
    )


engine = create_engine(
    DATABASE_URL,
    echo=False,
)

Base.metadata.create_all(engine)

observer = Observer(
    latitude=LATITUDE,
    longitude=LONGITUDE,
)


current_date = START_DATE

successful = 0
failed = 0

with Session(engine) as session:

    while current_date <= END_DATE:

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

            sunrise_time = sunrise_dt.strftime("%H:%M:%S")
            sunset_time = sunset_dt.strftime("%H:%M:%S")

            row = session.get(
                SunPosition,
                (current_date.isoformat(), LOCATION),
            )

            if row is None:

                row = SunPosition(
                    Date=current_date.isoformat(),
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

        except Exception as e:

            failed += 1

            print(
                f"{current_date}  ERROR: {e}"
            )

        current_date += timedelta(days=1)

        # Commit periodically instead of waiting 200 years of rows.
        if successful % 1000 == 0:
            session.commit()
            print(f"--- Committed {successful} rows ---")


    session.commit()


print()
print("Sun_Position population completed.")
print(f"Successful: {successful}")
print(f"Failed:     {failed}")
