#!/usr/bin/env python3

import sqlite3

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"

START_YEAR = 1927
END_YEAR = 2125


def populate_muharram(conn):
    conn.execute("DROP TABLE IF EXISTS Muharram")

    conn.execute("""
        CREATE TABLE Muharram (
            Date TEXT NOT NULL,
            Location TEXT NOT NULL,
            Hijri_Year TEXT NOT NULL,
            Hijri_Month TEXT NOT NULL,
            Hijri_Month_Name TEXT NOT NULL,
            Hijri_Day TEXT NOT NULL,
            Rule_Applied TEXT NOT NULL,
            PRIMARY KEY (Date, Location)
        )
    """)

    rows = conn.execute("""
        SELECT
            Gregorian_Date,
            Hijri_Year,
            Hijri_Month,
            Hijri_Month_Name,
            Hijri_Day
        FROM Hijri_Calendar
        WHERE Hijri_Month = '01'
          AND Hijri_Day = '10'
          AND Gregorian_Date BETWEEN ? AND ?
        ORDER BY Gregorian_Date
    """, (
        f"{START_YEAR}-01-01",
        f"{END_YEAR}-12-31"
    )).fetchall()

    for row in rows:
        conn.execute("""
            INSERT INTO Muharram (
                Date,
                Location,
                Hijri_Year,
                Hijri_Month,
                Hijri_Month_Name,
                Hijri_Day,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row[0],
            LOCATION,
            row[1],
            row[2],
            row[3],
            row[4],
            "10 Muharram (Ashura)"
        ))

    print(f"Muharram rows inserted: {len(rows)}")


def populate_eid_e_milad(conn):
    conn.execute("DROP TABLE IF EXISTS Eid_e_Milad")

    conn.execute("""
        CREATE TABLE Eid_e_Milad (
            Date TEXT NOT NULL,
            Location TEXT NOT NULL,
            Hijri_Year TEXT NOT NULL,
            Hijri_Month TEXT NOT NULL,
            Hijri_Month_Name TEXT NOT NULL,
            Hijri_Day TEXT NOT NULL,
            Rule_Applied TEXT NOT NULL,
            PRIMARY KEY (Date, Location)
        )
    """)

    rows = conn.execute("""
        SELECT
            Gregorian_Date,
            Hijri_Year,
            Hijri_Month,
            Hijri_Month_Name,
            Hijri_Day
        FROM Hijri_Calendar
        WHERE Hijri_Month = '03'
          AND Hijri_Day = '12'
          AND Gregorian_Date BETWEEN ? AND ?
        ORDER BY Gregorian_Date
    """, (
        f"{START_YEAR}-01-01",
        f"{END_YEAR}-12-31"
    )).fetchall()

    for row in rows:
        conn.execute("""
            INSERT INTO Eid_e_Milad (
                Date,
                Location,
                Hijri_Year,
                Hijri_Month,
                Hijri_Month_Name,
                Hijri_Day,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row[0],
            LOCATION,
            row[1],
            row[2],
            row[3],
            row[4],
            "12 Rabi al-Awwal (Eid-e-Milad / Barah Wafat)"
        ))

    print(f"Eid-e-Milad rows inserted: {len(rows)}")


def main():
    conn = sqlite3.connect(DB_PATH)

    try:
        populate_muharram(conn)
        populate_eid_e_milad(conn)
        conn.commit()

        print("\nMuharram:")
        for row in conn.execute("""
            SELECT Date, Hijri_Year, Hijri_Month_Name, Hijri_Day
            FROM Muharram
            ORDER BY Date
        """):
            print(" | ".join(row))

        print("\nEid-e-Milad:")
        for row in conn.execute("""
            SELECT Date, Hijri_Year, Hijri_Month_Name, Hijri_Day
            FROM Eid_e_Milad
            ORDER BY Date
        """):
            print(" | ".join(row))

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
