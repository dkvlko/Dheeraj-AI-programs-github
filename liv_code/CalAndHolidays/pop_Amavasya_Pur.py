#!/usr/bin/env python3

import sqlite3
from pathlib import Path


DATABASE = Path(
    "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"
)


def create_amavasya_purnima_table(conn):
    conn.execute("""
        DROP TABLE IF EXISTS Amavasya_Purnima;
    """)

    conn.execute("""
        CREATE TABLE Amavasya_Purnima (
            Date_Time_UTC TEXT NOT NULL,
            Date_Time_Local TEXT NOT NULL,

            Location TEXT NOT NULL,

            Latitude REAL NOT NULL,
            Longitude REAL NOT NULL,

            Sun_Longitude REAL NOT NULL,
            Moon_Longitude REAL NOT NULL,

            Angular_Separation REAL NOT NULL,

            Tithi TEXT NOT NULL,
            Paksha TEXT NOT NULL,

            Lunar_Phase TEXT NOT NULL,

            PRIMARY KEY (Date_Time_UTC, Location)
        );
    """)

    conn.commit()


def populate_amavasya_purnima(conn):

    select_sql = """
        SELECT
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
        FROM Sun_Moon_Position
        ORDER BY Date_Time_UTC, Location;
    """

    insert_sql = """
        INSERT INTO Amavasya_Purnima (
            Date_Time_UTC,
            Date_Time_Local,
            Location,
            Latitude,
            Longitude,
            Sun_Longitude,
            Moon_Longitude,
            Angular_Separation,
            Tithi,
            Paksha,
            Lunar_Phase
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    cursor = conn.execute(select_sql)

    batch = []
    batch_size = 1000

    count = 0

    for row in cursor:

        (
            date_time_utc,
            date_time_local,
            location,
            latitude,
            longitude,
            sun_longitude,
            moon_longitude,
            angular_separation,
            tithi,
            paksha,
        ) = row

        if paksha == "Shukla" and tithi == "15":
            lunar_phase = "Purnima"

        elif paksha == "Krishna" and tithi == "15":
            lunar_phase = "Amavasya"

        else:
            lunar_phase = "Other"

        batch.append((
            date_time_utc,
            date_time_local,
            location,
            latitude,
            longitude,
            sun_longitude,
            moon_longitude,
            angular_separation,
            tithi,
            paksha,
            lunar_phase,
        ))

        if len(batch) >= batch_size:
            conn.executemany(insert_sql, batch)
            conn.commit()

            count += len(batch)
            print(f"Inserted {count:,} records")

            batch.clear()

    if batch:
        conn.executemany(insert_sql, batch)
        conn.commit()

        count += len(batch)

    print(f"Total records inserted: {count:,}")


def main():

    print(f"Database: {DATABASE}")

    with sqlite3.connect(DATABASE) as conn:

        create_amavasya_purnima_table(conn)

        populate_amavasya_purnima(conn)

    print("Amavasya_Purnima table created successfully.")


if __name__ == "__main__":
    main()
