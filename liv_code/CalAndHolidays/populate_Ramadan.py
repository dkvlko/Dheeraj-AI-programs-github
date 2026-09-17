#!/usr/bin/env python3

import sqlite3
import math
from datetime import datetime, timedelta


DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

START_GREGORIAN_YEAR = 1927
END_GREGORIAN_YEAR = 2125


# ============================================================
# ISLAMIC TABULAR CALENDAR
# ============================================================

ISLAMIC_EPOCH = 1948439.5


def islamic_to_jd(year, month, day):
    """
    Standard arithmetic/tabular Islamic calendar.

    Month:
        1 = Muharram
        ...
        9 = Ramadan
        10 = Shawwal
    """

    return (
        day
        + math.ceil(29.5 * (month - 1))
        + (year - 1) * 354
        + math.floor((3 + 11 * year) / 30)
        + ISLAMIC_EPOCH
        - 0.5
    )


def jd_to_gregorian(jd):
    """
    Julian Day -> Gregorian date.
    """

    z = int(jd + 0.5)
    f = (jd + 0.5) - z

    if z < 2299161:
        a = z
    else:
        alpha = int(
            (z - 1867216.25) / 36524.25
        )

        a = (
            z
            + 1
            + alpha
            - int(alpha / 4)
        )

    b = a + 1524

    c = int(
        (b - 122.1) / 365.25
    )

    d = int(
        365.25 * c
    )

    e = int(
        (b - d) / 30.6001
    )

    day = (
        b
        - d
        - int(30.6001 * e)
        + f
    )

    month = (
        e - 1
        if e < 14
        else e - 13
    )

    year = (
        c - 4716
        if month > 2
        else c - 4715
    )

    return datetime(
        year,
        month,
        int(day)
    ).date()


def hijri_to_gregorian(
    hijri_year,
    hijri_month,
    hijri_day
):
    jd = islamic_to_jd(
        hijri_year,
        hijri_month,
        hijri_day
    )

    return jd_to_gregorian(jd)


# ============================================================
# FIND HIJRI YEARS COVERING REQUESTED GREGORIAN RANGE
# ============================================================

def generate_ramadan_rows():

    rows = []

    # Approximate range of Hijri years that can contain
    # Ramadan starts in 1927–2125.
    #
    # We deliberately search a little wider and then filter.

    for hijri_year in range(
        1340,
        1555
    ):

        ramadan_start = hijri_to_gregorian(
            hijri_year,
            9,
            1
        )

        if not (
            START_GREGORIAN_YEAR
            <= ramadan_start.year
            <= END_GREGORIAN_YEAR
        ):
            continue

        # Ramadan has 29 or 30 days in the tabular
        # calendar depending on the length assigned to
        # the month in that Hijri year.
        #
        # In the standard arithmetic calendar, month 9
        # is normally 30 days.

        ramadan_start_jd = islamic_to_jd(
            hijri_year,
            9,
            1
        )

        shawwal_start_jd = islamic_to_jd(
            hijri_year,
            10,
            1
        )

        shawwal_start = jd_to_gregorian(
            shawwal_start_jd
        )

        # Last daytime date of Ramadan.
        ramadan_end = (
            shawwal_start
            - timedelta(days=1)
        )

        ramadan_days = (
            shawwal_start
            - ramadan_start
        ).days

        rows.append(
            (
                hijri_year,
                ramadan_start.year,
                ramadan_start.isoformat(),
                ramadan_end.isoformat(),
                shawwal_start.isoformat(),
                shawwal_start.isoformat(),
                ramadan_days,
                "Tabular Islamic",
                "Deterministic Ramadan anchor",
            )
        )

    return rows


# ============================================================
# DATABASE
# ============================================================

def main():

    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS Ramadan (
            Hijri_Year TEXT NOT NULL,
            Gregorian_Year INTEGER NOT NULL,

            Ramadan_Start_Date TEXT NOT NULL,
            Ramadan_End_Date TEXT NOT NULL,

            Shawwal_Start_Date TEXT NOT NULL,
            Tabular_Eid_Ul_Fitr_Date TEXT NOT NULL,

            Ramadan_Days INTEGER NOT NULL
                CHECK (Ramadan_Days IN (29, 30)),

            Calendar_System TEXT NOT NULL,
            Anchor_Type TEXT NOT NULL,

            PRIMARY KEY (Hijri_Year)
        )
        """
    )

    conn.execute(
        "DELETE FROM Ramadan"
    )

    rows = generate_ramadan_rows()

    conn.executemany(
        """
        INSERT INTO Ramadan (
            Hijri_Year,
            Gregorian_Year,
            Ramadan_Start_Date,
            Ramadan_End_Date,
            Shawwal_Start_Date,
            Tabular_Eid_Ul_Fitr_Date,
            Ramadan_Days,
            Calendar_System,
            Anchor_Type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows
    )

    conn.commit()

    print(
        f"Inserted {len(rows)} Ramadan records."
    )

    # --------------------------------------------------------
    # Show first and last records
    # --------------------------------------------------------

    print()
    print("First 5 records:")

    for row in conn.execute(
        """
        SELECT
            Hijri_Year,
            Ramadan_Start_Date,
            Ramadan_End_Date,
            Shawwal_Start_Date
        FROM Ramadan
        ORDER BY CAST(Hijri_Year AS INTEGER)
        LIMIT 5
        """
    ):
        print(row)

    print()
    print("Last 5 records:")

    for row in conn.execute(
        """
        SELECT
            Hijri_Year,
            Ramadan_Start_Date,
            Ramadan_End_Date,
            Shawwal_Start_Date
        FROM Ramadan
        ORDER BY CAST(Hijri_Year AS INTEGER) DESC
        LIMIT 5
        """
    ):
        print(row)

    print()
    print("Gregorian years containing two Ramadan starts:")

    for row in conn.execute(
        """
        SELECT
            Gregorian_Year,
            COUNT(*) AS Ramadan_Count
        FROM Ramadan
        GROUP BY Gregorian_Year
        HAVING COUNT(*) > 1
        ORDER BY Gregorian_Year
        """
    ):
        print(row)

    conn.close()


if __name__ == "__main__":
    main()
