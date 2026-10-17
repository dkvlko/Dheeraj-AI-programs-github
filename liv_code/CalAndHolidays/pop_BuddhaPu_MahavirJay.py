#!/usr/bin/env python3

import sqlite3
from datetime import datetime


# ============================================================
# Configuration
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"

START_YEAR = 1925
END_YEAR = 2125


# ============================================================
# Helper
# ============================================================

def get_tithi_transition(conn, civil_date, tithi, paksha):
    """
    Find the exact Tithi_Transition interval containing the
    local sunrise on the specified civil date.

    Returns:
        (Start_Date_Time_Local, End_Date_Time_Local)
    """

    sun = conn.execute(
        """
        SELECT Sunrise_Time
        FROM Sun_Position
        WHERE Date = ?
          AND Location = ?
        """,
        (civil_date, LOCATION)
    ).fetchone()

    if sun is None:
        raise RuntimeError(
            f"No Sun_Position found for {civil_date}"
        )

    sunrise = datetime.strptime(
        f"{civil_date} {sun["Sunrise_Time"]}",
        "%Y-%m-%d %H:%M:%S"
    )

    # Your Tithi_Transition local timestamps are currently
    # stored as YYYY-MM-DD HH:MM:SS.
    sunrise_text = sunrise.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    row = conn.execute(
        """
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local
        FROM Tithi_Transition
        WHERE Location = ?
          AND Tithi = ?
          AND Paksha = ?
          AND Start_Date_Time_Local <= ?
          AND End_Date_Time_Local > ?
        ORDER BY Start_Date_Time_Local DESC
        LIMIT 1
        """,
        (
            LOCATION,
            tithi,
            paksha,
            sunrise_text,
            sunrise_text
        )
    ).fetchone()

    if row is None:
        raise RuntimeError(
            f"No {paksha} Tithi {tithi} transition "
            f"found at sunrise on {civil_date}"
        )

    return (
        row["Start_Date_Time_Local"],
        row["End_Date_Time_Local"]
    )


# ============================================================
# Main
# ============================================================

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

try:

    # --------------------------------------------------------
    # Buddha Purnima
    #
    # Vaishakha = Masa 02
    # Shukla Purnima = Tithi 15
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("BUDDHA PURNIMA")
    print("=" * 72)

    buddha_rows = conn.execute(
        """
        SELECT
            Year,
            Month,
            Date,
            Masa,
            Adhika_Masa,
            Tithi,
            Paksha
        FROM Hindu_Calendar
        WHERE CAST(Year AS INTEGER) BETWEEN ? AND ?
          AND Masa = '02'
          AND Adhika_Masa = 0
          AND Tithi = '15'
          AND Paksha = 'Shukla'
        ORDER BY Year, Month, Date
        """,
        (START_YEAR, END_YEAR)
    ).fetchall()

    buddha_count = 0

    for row in buddha_rows:

        civil_date = (
            f"{row['Year']}-"
            f"{row['Month']}-"
            f"{row['Date']}"
        )

        purnima_start, purnima_end = get_tithi_transition(
            conn,
            civil_date,
            tithi="15",
            paksha="Shukla"
        )

        print(
            f"{civil_date} | "
            f"Purnima: {purnima_start} -> {purnima_end}"
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO Buddha_Purnima (
                Date,
                Location,
                Purnima_Start_Local,
                Purnima_End_Local
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                civil_date,
                LOCATION,
                purnima_start,
                purnima_end
            )
        )

        buddha_count += 1

    # --------------------------------------------------------
    # Mahavir Jayanti
    #
    # Chaitra = Masa 01
    # Shukla Trayodashi = Tithi 13
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("MAHAVIR JAYANTI")
    print("=" * 72)

    mahavir_rows = conn.execute(
        """
        SELECT
            Year,
            Month,
            Date,
            Masa,
            Adhika_Masa,
            Tithi,
            Paksha
        FROM Hindu_Calendar
        WHERE CAST(Year AS INTEGER) BETWEEN ? AND ?
          AND Masa = '01'
          AND Adhika_Masa = 0
          AND Tithi = '13'
          AND Paksha = 'Shukla'
        ORDER BY Year, Month, Date
        """,
        (START_YEAR, END_YEAR)
    ).fetchall()

    mahavir_count = 0

    for row in mahavir_rows:

        civil_date = (
            f"{row['Year']}-"
            f"{row['Month']}-"
            f"{row['Date']}"
        )

        trayodashi_start, trayodashi_end = (
            get_tithi_transition(
                conn,
                civil_date,
                tithi="13",
                paksha="Shukla"
            )
        )

        print(
            f"{civil_date} | "
            f"Trayodashi: "
            f"{trayodashi_start} -> {trayodashi_end}"
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO Mahavir_Jayanti (
                Date,
                Location,
                Trayodashi_Start_Local,
                Trayodashi_End_Local
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                civil_date,
                LOCATION,
                trayodashi_start,
                trayodashi_end
            )
        )

        mahavir_count += 1

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    conn.commit()

    print()
    print("=" * 72)
    print("Population completed.")
    print(f"Buddha Purnima records : {buddha_count}")
    print(f"Mahavir Jayanti records: {mahavir_count}")
    print("=" * 72)

finally:
    conn.close()
