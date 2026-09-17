#!/usr/bin/env python3

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo


# ============================================================
# Configuration
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"
TIMEZONE = ZoneInfo("Asia/Kolkata")

START_YEAR = 1927
END_YEAR = 2125

START_DATE = f"{START_YEAR}-01-01"
END_DATE = f"{END_YEAR + 1}-01-01"

# We need a little extra range around the test period to obtain
# the Purnima immediately before and immediately after it.
BOUNDARY_START = f"{START_YEAR - 1}-01-01"
BOUNDARY_END = f"{END_YEAR + 2}-01-01"


# ============================================================
# Datetime helper
# ============================================================

def parse_datetime(value):

    dt = datetime.fromisoformat(value.strip())

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TIMEZONE)
    else:
        dt = dt.astimezone(TIMEZONE)

    return dt


# ============================================================
# Create table
# ============================================================

def create_table(conn):

    conn.execute("""
        DROP TABLE IF EXISTS Purnimanta_Tithi_Transition
    """)

    conn.execute("""
        CREATE TABLE Purnimanta_Tithi_Transition (

            Start_Date_Time_UTC TEXT NOT NULL,
            End_Date_Time_UTC TEXT NOT NULL,

            Start_Date_Time_Local TEXT NOT NULL,
            End_Date_Time_Local TEXT NOT NULL,

            Location TEXT NOT NULL,

            Latitude REAL NOT NULL,
            Longitude REAL NOT NULL,

            Angular_Separation_Start REAL NOT NULL,
            Angular_Separation_End REAL NOT NULL,

            Tithi TEXT NOT NULL,
            Paksha TEXT NOT NULL,

            Masa TEXT NOT NULL,
            Masa_Type TEXT NOT NULL,

            PRIMARY KEY (
                Start_Date_Time_UTC,
                Location
            )
        )
    """)

    conn.commit()


# ============================================================
# Read only the required Tithi transitions
# ============================================================

def get_tithi_transitions(conn):

    rows = conn.execute("""
        SELECT
            Start_Date_Time_UTC,
            End_Date_Time_UTC,

            Start_Date_Time_Local,
            End_Date_Time_Local,

            Location,

            Latitude,
            Longitude,

            Angular_Separation_Start,
            Angular_Separation_End,

            Tithi,
            Paksha

        FROM Tithi_Transition

        WHERE Location = ?

          AND Start_Date_Time_Local >= ?
          AND Start_Date_Time_Local < ?

        ORDER BY Start_Date_Time_Local
    """, (
        LOCATION,
        BOUNDARY_START,
        BOUNDARY_END
    )).fetchall()

    return rows


# ============================================================
# Find Purnima boundaries
# ============================================================

def find_purnima_boundaries(rows):

    purnimas = []

    for row in rows:

        if (
            row["Tithi"] == "15"
            and row["Paksha"] == "Shukla"
        ):

            purnimas.append({
                "end_utc": parse_datetime(
                    row["End_Date_Time_UTC"]
                ),

                "end_local": parse_datetime(
                    row["End_Date_Time_Local"]
                ),

                "row": row
            })

    purnimas.sort(key=lambda x: x["end_local"])

    return purnimas


# ============================================================
# Find Amanta Masa containing a datetime
# ============================================================

def find_amanta_masa(conn, dt):

    row = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Masa_Number,
            Masa_English,
            Masa_Hindi,
            Masa_Type

        FROM Masa_Transition

        WHERE Location = ?

          AND Start_Date_Time_Local <= ?
          AND End_Date_Time_Local > ?

        ORDER BY Start_Date_Time_Local DESC

        LIMIT 1
    """, (
        LOCATION,
        dt.isoformat(),
        dt.isoformat()
    )).fetchone()

    if row is None:
        return None

    return {
        "number": row["Masa_Number"],
        "english": row["Masa_English"],
        "hindi": row["Masa_Hindi"],
        "type": row["Masa_Type"]
    }


# ============================================================
# Build Purnimanta months
# ============================================================

def build_purnimanta_months(conn, purnimas):

    months = []

    for i in range(len(purnimas) - 1):

        previous_purnima = purnimas[i]
        next_purnima = purnimas[i + 1]

        month_start = previous_purnima["end_utc"]
        month_end = next_purnima["end_utc"]

        # ----------------------------------------------------
        # We assign the Purnimanta month name using the
        # Amanta Masa containing the ENDING Purnima.
        # ----------------------------------------------------

        masa = find_amanta_masa(
            conn,
            next_purnima["end_local"]
        )

        if masa is None:
            print(
                "WARNING: No Amanta Masa found for "
                f"Purnima {next_purnima['end_local']}"
            )
            continue

        # ----------------------------------------------------
        # Keep only Purnimanta months that overlap the
        # requested test period.
        # ----------------------------------------------------

        if month_end <= parse_datetime(
            f"{START_DATE}T00:00:00+05:30"
        ):
            continue

        if month_start >= parse_datetime(
            f"{END_DATE}T00:00:00+05:30"
        ):
            continue

        months.append({
            "start": month_start,
            "end": month_end,

            "masa": masa["number"],
            "masa_english": masa["english"],
            "masa_hindi": masa["hindi"],
            "masa_type": masa["type"]
        })

    return months


# ============================================================
# Populate table
# ============================================================

def populate_purnimanta(conn, rows, months):

    inserted = 0

    for month in months:

        month_start = month["start"]
        month_end = month["end"]

        for row in rows:

            row_start = parse_datetime(
                row["Start_Date_Time_UTC"]
            )

            row_end = parse_datetime(
                row["End_Date_Time_UTC"]
            )

            # Tithi must belong completely to this
            # Purnimanta month.
            if not (
                row_start >= month_start
                and row_end <= month_end
            ):
                continue

            # Only populate requested Gregorian years.
            if not (
                START_DATE
                <= row["Start_Date_Time_Local"][:10]
                < END_DATE
            ):
                continue

            conn.execute("""
                INSERT INTO Purnimanta_Tithi_Transition (

                    Start_Date_Time_UTC,
                    End_Date_Time_UTC,

                    Start_Date_Time_Local,
                    End_Date_Time_Local,

                    Location,

                    Latitude,
                    Longitude,

                    Angular_Separation_Start,
                    Angular_Separation_End,

                    Tithi,
                    Paksha,

                    Masa,
                    Masa_Type

                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (

                row["Start_Date_Time_UTC"],
                row["End_Date_Time_UTC"],

                row["Start_Date_Time_Local"],
                row["End_Date_Time_Local"],

                row["Location"],

                row["Latitude"],
                row["Longitude"],

                row["Angular_Separation_Start"],
                row["Angular_Separation_End"],

                row["Tithi"],
                row["Paksha"],

                month["masa"],
                month["masa_type"]
            ))

            inserted += 1

    conn.commit()

    return inserted


# ============================================================
# Show Purnimanta months
# ============================================================

def show_months(months):

    print()
    print("=" * 90)
    print("PURNIMANTA MONTHS")
    print("=" * 90)

    for month in months:

        print(
            f"{month['start'].isoformat()} -> "
            f"{month['end'].isoformat()} | "
            f"Masa={month['masa']} "
            f"({month['masa_english']}) | "
            f"{month['masa_type']}"
        )


# ============================================================
# Show Amavasyas
# ============================================================

def show_amavasya(conn):

    print()
    print("=" * 90)
    print("PURNIMANTA AMAVASYA")
    print("=" * 90)

    rows = conn.execute("""
        SELECT
            Start_Date_Time_Local,
            End_Date_Time_Local,
            Masa,
            Masa_Type

        FROM Purnimanta_Tithi_Transition

        WHERE Tithi = '15'
          AND Paksha = 'Krishna'

        ORDER BY Start_Date_Time_Local
    """).fetchall()

    for row in rows:

        print(
            f"{row['Start_Date_Time_Local']} -> "
            f"{row['End_Date_Time_Local']} | "
            f"Masa={row['Masa']} | "
            f"Type={row['Masa_Type']}"
        )


# ============================================================
# Validation
# ============================================================

def validate(conn):

    print()
    print("=" * 90)
    print("VALIDATION")
    print("=" * 90)

    count = conn.execute("""
        SELECT COUNT(*)
        FROM Purnimanta_Tithi_Transition
    """).fetchone()[0]

    print(
        f"Purnimanta_Tithi_Transition rows: {count}"
    )

    print()

    # Count by year
    rows = conn.execute("""
        SELECT
            substr(Start_Date_Time_Local, 1, 4) AS Year,
            COUNT(*) AS Count

        FROM Purnimanta_Tithi_Transition

        GROUP BY Year
        ORDER BY Year
    """).fetchall()

    print("Rows by year:")

    for row in rows:
        print(
            f"  {row['Year']} : {row['Count']}"
        )

    print()

    # Count by Masa
    rows = conn.execute("""
        SELECT
            Masa,
            Masa_Type,
            COUNT(*) AS Count

        FROM Purnimanta_Tithi_Transition

        GROUP BY Masa, Masa_Type

        ORDER BY Masa, Masa_Type
    """).fetchall()

    print("Rows by Masa:")

    for row in rows:
        print(
            f"  Masa={row['Masa']} | "
            f"Type={row['Masa_Type']} | "
            f"Rows={row['Count']}"
        )


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 90)
    print("PURNIMANTA TITHI TRANSITION GENERATOR")
    print("=" * 90)

    print(f"Database       : {DB_PATH}")
    print(f"Location       : {LOCATION}")
    print(
        f"Test range     : "
        f"{START_YEAR} - {END_YEAR}"
    )

    print(
        f"Source range   : "
        f"{BOUNDARY_START} to {BOUNDARY_END}"
    )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:

        create_table(conn)

        # ----------------------------------------------------
        # Load ONLY the required source rows.
        # ----------------------------------------------------

        rows = get_tithi_transitions(conn)

        print()
        print(
            "Tithi_Transition rows loaded: "
            f"{len(rows)}"
        )

        # ----------------------------------------------------
        # Find Purnima boundaries.
        # ----------------------------------------------------

        purnimas = find_purnima_boundaries(rows)

        print()
        print(
            "Purnima boundaries found: "
            f"{len(purnimas)}"
        )

        for p in purnimas:

            print(
                f"  {p['end_local'].isoformat()}"
            )

        # ----------------------------------------------------
        # Construct Purnimanta months.
        # ----------------------------------------------------

        months = build_purnimanta_months(
            conn,
            purnimas
        )

        show_months(months)

        # ----------------------------------------------------
        # Populate.
        # ----------------------------------------------------

        inserted = populate_purnimanta(
            conn,
            rows,
            months
        )

        print()
        print(
            f"Inserted {inserted} rows into "
            "Purnimanta_Tithi_Transition"
        )

        # ----------------------------------------------------
        # Validation.
        # ----------------------------------------------------

        validate(conn)

        show_amavasya(conn)

        print()
        print("Completed successfully.")

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


if __name__ == "__main__":
    main()
