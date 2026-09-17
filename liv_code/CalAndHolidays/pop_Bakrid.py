#!/usr/bin/env python3

import sqlite3

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"

START_YEAR = 1927
END_YEAR = 2125


def main():

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("""
            DROP TABLE IF EXISTS Bakrid
        """)

        conn.execute("""
            CREATE TABLE Bakrid (
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
            WHERE Hijri_Month = '12'
              AND Hijri_Day = '10'
              AND Gregorian_Date BETWEEN ? AND ?
            ORDER BY Gregorian_Date
        """, (
            f"{START_YEAR}-01-01",
            f"{END_YEAR}-12-31",
        )).fetchall()

        if not rows:
            raise RuntimeError(
                f"No Bakrid dates found between "
                f"{START_YEAR} and {END_YEAR}."
            )

        insert_rows = []

        for row in rows:

            gregorian_date = row[0]
            hijri_year = row[1]
            hijri_month = row[2]
            hijri_month_name = row[3]
            hijri_day = row[4]

            insert_rows.append((
                gregorian_date,
                LOCATION,
                hijri_year,
                hijri_month,
                hijri_month_name,
                hijri_day,
                "10 Dhu al-Hijjah derived from Hijri_Calendar"
            ))

        conn.executemany("""
            INSERT INTO Bakrid (
                Date,
                Location,
                Hijri_Year,
                Hijri_Month,
                Hijri_Month_Name,
                Hijri_Day,
                Rule_Applied
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, insert_rows)

        conn.commit()

        print("=" * 60)
        print("BAKRID TABLE POPULATED")
        print("=" * 60)

        for row in insert_rows:
            print(
                f"Hijri {row[2]} "
                f"10 Dhu al-Hijjah -> {row[0]}"
            )

        print()
        print(f"Rows inserted: {len(insert_rows)}")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
