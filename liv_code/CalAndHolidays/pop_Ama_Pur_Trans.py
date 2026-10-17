
#!/usr/bin/env python3

import sqlite3
from pathlib import Path


DATABASE = Path(
    "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"
)


def create_table(conn):
    conn.execute("""
        DROP TABLE IF EXISTS Amavasya_Purnima_Transition;
    """)

    conn.execute("""
        CREATE TABLE Amavasya_Purnima_Transition (

            Start_Date_Time_UTC TEXT NOT NULL,
            End_Date_Time_UTC TEXT NOT NULL,

            Start_Date_Time_Local TEXT NOT NULL,
            End_Date_Time_Local TEXT NOT NULL,

            Location TEXT NOT NULL,

            Latitude REAL NOT NULL,
            Longitude REAL NOT NULL,

            Phase TEXT NOT NULL,

            Angular_Separation_Start REAL NOT NULL,
            Angular_Separation_End REAL NOT NULL,

            PRIMARY KEY (
                Start_Date_Time_UTC,
                Location
            )
        );
    """)

    conn.commit()


def populate_table(conn):

    select_sql = """
        SELECT
            Date_Time_UTC,
            Date_Time_Local,
            Location,
            Latitude,
            Longitude,
            Angular_Separation,
            Lunar_Phase
        FROM Amavasya_Purnima
        WHERE Lunar_Phase IN ('Amavasya', 'Purnima')
        ORDER BY
            Location,
            Date_Time_UTC;
    """

    rows = conn.execute(select_sql).fetchall()

    insert_sql = """
        INSERT INTO Amavasya_Purnima_Transition (
            Start_Date_Time_UTC,
            End_Date_Time_UTC,

            Start_Date_Time_Local,
            End_Date_Time_Local,

            Location,

            Latitude,
            Longitude,

            Phase,

            Angular_Separation_Start,
            Angular_Separation_End
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    transitions = []

    current = None

    for row in rows:

        (
            date_time_utc,
            date_time_local,
            location,
            latitude,
            longitude,
            angular_separation,
            phase,
        ) = row

        # Start a new phase
        if current is None:

            current = {
                "start_utc": date_time_utc,
                "start_local": date_time_local,
                "location": location,
                "latitude": latitude,
                "longitude": longitude,
                "phase": phase,
                "angle_start": angular_separation,
                "end_utc": date_time_utc,
                "end_local": date_time_local,
                "angle_end": angular_separation,
            }

            continue

        # Same location and same phase:
        # extend the current interval.
        if (
            location == current["location"]
            and phase == current["phase"]
        ):

            current["end_utc"] = date_time_utc
            current["end_local"] = date_time_local
            current["angle_end"] = angular_separation

            continue

        # Phase changed.
        transitions.append((
            current["start_utc"],
            current["end_utc"],
            current["start_local"],
            current["end_local"],
            current["location"],
            current["latitude"],
            current["longitude"],
            current["phase"],
            current["angle_start"],
            current["angle_end"],
        ))

        # Start new phase
        current = {
            "start_utc": date_time_utc,
            "start_local": date_time_local,
            "location": location,
            "latitude": latitude,
            "longitude": longitude,
            "phase": phase,
            "angle_start": angular_separation,
            "end_utc": date_time_utc,
            "end_local": date_time_local,
            "angle_end": angular_separation,
        }

    # Add final phase
    if current is not None:

        transitions.append((
            current["start_utc"],
            current["end_utc"],
            current["start_local"],
            current["end_local"],
            current["location"],
            current["latitude"],
            current["longitude"],
            current["phase"],
            current["angle_start"],
            current["angle_end"],
        ))

    conn.executemany(
        insert_sql,
        transitions
    )

    conn.commit()

    print(
        f"Inserted {len(transitions):,} "
        f"Amavasya/Purnima transitions."
    )


def main():

    print(f"Database: {DATABASE}")

    with sqlite3.connect(DATABASE) as conn:

        create_table(conn)

        populate_table(conn)

    print(
        "Amavasya_Purnima_Transition "
        "table created successfully."
    )


if __name__ == "__main__":
    main()
