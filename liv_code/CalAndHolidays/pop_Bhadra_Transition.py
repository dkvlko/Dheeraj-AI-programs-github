
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# Configuration
# ============================================================

DB_PATH = "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"

LOCATION = "Lucknow, Uttar Pradesh, India"
LATITUDE = 26.8467
LONGITUDE = 80.9462

TIMEZONE = ZoneInfo("Asia/Kolkata")

START_DATE = "1926-01-01T00:00:00+05:30"
END_DATE   = "2126-01-01T00:00:00+05:30"


# ============================================================
# Bhadra rules
#
# Vishti occurs on:
#
# Shukla:
#   Chaturthi  = Tithi 04
#   Ashtami    = Tithi 08
#   Ekadashi   = Tithi 11
#   Purnima    = Tithi 15
#
# Krishna:
#   Tritiya    = Tithi 03
#   Saptami    = Tithi 07
#   Dashami    = Tithi 10
#   Chaturdashi= Tithi 14
#
# The quarter containing Bhadra Mukha:
#
# Shukla:
#   04 -> Q1
#   08 -> Q2
#   11 -> Q3
#   15 -> Q4
#
# Krishna:
#   14 -> Q1
#   10 -> Q2
#   07 -> Q3
#   03 -> Q4
#
# The quarter containing Bhadra Puccha:
#
# Shukla:
#   04 -> Q4
#   08 -> Q1
#   11 -> Q2
#   15 -> Q3
#
# Krishna:
#   14 -> Q4
#   10 -> Q1
#   07 -> Q2
#   03 -> Q3
#
# Mukha = first 5/30 of the actual Vishti duration
# Puccha = last 3/30 of the actual Vishti duration
#
# This scales the traditional 5-ghati and 3-ghati
# definitions to the actual Karana duration.
# ============================================================

MUKHA_QUARTER = {
    ("Shukla", 4):  1,
    ("Shukla", 8):  2,
    ("Shukla", 11): 3,
    ("Shukla", 15): 4,

    ("Krishna", 14): 1,
    ("Krishna", 10): 2,
    ("Krishna", 7):  3,
    ("Krishna", 3):  4,
}

PUCCHA_QUARTER = {
    ("Shukla", 4):  4,
    ("Shukla", 8):  1,
    ("Shukla", 11): 2,
    ("Shukla", 15): 3,

    ("Krishna", 14): 4,
    ("Krishna", 10): 1,
    ("Krishna", 7):  2,
    ("Krishna", 3):  3,
}


# ============================================================
# Helpers
# ============================================================

def parse_datetime(value: str) -> datetime:
    """
    Parse ISO datetime stored in SQLite.

    Handles values such as:
        2027-03-21T18:22:02.466912+05:30
    """
    return datetime.fromisoformat(value)


def format_datetime(dt: datetime) -> str:
    """
    Store datetime in ISO-8601 format including timezone.
    """
    return dt.isoformat(timespec="microseconds")


def add_fraction(start: datetime,
                 end: datetime,
                 fraction: float) -> datetime:
    """
    Return:

        start + fraction * (end - start)

    Using timedelta multiplication avoids assuming that
    every Karana lasts exactly 12 hours.
    """
    return start + (end - start) * fraction


# ============================================================
# Main
# ============================================================

def populate_bhadra_transition() -> None:

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        # ----------------------------------------------------
        # Remove only the requested period.
        #
        # This makes the script safely rerunnable.
        # ----------------------------------------------------

        conn.execute(
            """
            DELETE FROM Bhadra_Transition
            WHERE Location = ?
              AND Start_Date_Time_Local >= ?
              AND Start_Date_Time_Local < ?
            """,
            (
                LOCATION,
                START_DATE,
                END_DATE,
            ),
        )

        # ----------------------------------------------------
        # Get all Vishti / Bhadra intervals.
        #
        # We use Karana_Transition as the astronomical source.
        # ----------------------------------------------------

        rows = conn.execute(
            """
            SELECT
                Start_Date_Time_UTC,
                End_Date_Time_UTC,
                Start_Date_Time_Local,
                End_Date_Time_Local,
                Location,
                Angular_Separation_Start,
                Angular_Separation_End,
                Karana_Number,
                Karana,
                Is_Bhadra
            FROM Karana_Transition
            WHERE Location = ?
              AND Is_Bhadra = 1
              AND Start_Date_Time_Local >= ?
              AND Start_Date_Time_Local < ?
            ORDER BY Start_Date_Time_UTC
            """,
            (
                LOCATION,
                START_DATE,
                END_DATE,
            ),
        ).fetchall()

        print(f"Found {len(rows):,} Bhadra intervals.")

        insert_rows = []

        for row in rows:

            (
                start_utc,
                end_utc,
                start_local,
                end_local,
                location,
                angular_start,
                angular_end,
                karana_number,
                karana,
                is_bhadra,
            ) = row

            # ------------------------------------------------
            # Parse local interval.
            # ------------------------------------------------

            start = parse_datetime(start_local)
            end = parse_datetime(end_local)

            duration = end - start

            if duration.total_seconds() <= 0:
                raise ValueError(
                    f"Invalid Bhadra interval:\n"
                    f"{start_local} -> {end_local}"
                )

            # ------------------------------------------------
            # Determine the tithi containing this Vishti.
            #
            # Each Karana is 6 degrees.
            #
            # Vishti positions:
            #
            # 08 = Shukla 04, second half
            # 15 = Shukla 08, first half
            # 22 = Shukla 11, second half
            # 29 = Shukla 15, first half
            # 36 = Krishna 03, second half
            # 43 = Krishna 07, first half
            # 50 = Krishna 10, second half
            # 57 = Krishna 14, first half
            #
            # We can derive this directly from the Karana
            # position.
            # ------------------------------------------------

            karana_num = int(karana_number)

            tithi_info = {
                8:  ("Shukla", 4),
                15: ("Shukla", 8),
                22: ("Shukla", 11),
                29: ("Shukla", 15),

                36: ("Krishna", 3),
                43: ("Krishna", 7),
                50: ("Krishna", 10),
                57: ("Krishna", 14),
            }

            if karana_num not in tithi_info:
                raise ValueError(
                    f"Unexpected Bhadra Karana number: "
                    f"{karana_num}"
                )

            paksha, tithi = tithi_info[karana_num]

            # ------------------------------------------------
            # Find the quarter containing Mukha/Puccha.
            # ------------------------------------------------

            mukha_quarter = MUKHA_QUARTER[(paksha, tithi)]
            puccha_quarter = PUCCHA_QUARTER[(paksha, tithi)]

            # ------------------------------------------------
            # Divide actual Vishti duration into four equal
            # quarters.
            # ------------------------------------------------

            quarter_duration = duration / 4

            q1_start = start
            q1_end = start + quarter_duration

            q2_start = q1_end
            q2_end = start + quarter_duration * 2

            q3_start = q2_end
            q3_end = start + quarter_duration * 3

            q4_start = q3_end
            q4_end = end

            quarters = {
                1: (q1_start, q1_end),
                2: (q2_start, q2_end),
                3: (q3_start, q3_end),
                4: (q4_start, q4_end),
            }

            # ------------------------------------------------
            # Traditional scaling:
            #
            # Mukha:
            #   first 5 ghatis of a 30-ghati Karana
            #   = 5/30 = 1/6 of the Karana.
            #
            # Puccha:
            #   last 3 ghatis of a 30-ghati Karana
            #   = 3/30 = 1/10 of the Karana.
            #
            # Since Mukha starts at the beginning of its
            # designated quarter:
            #
            #     quarter_start -> quarter_start + 1/6 Karana
            #
            # Since Puccha ends at the end of its designated
            # quarter:
            #
            #     quarter_end - 1/10 Karana -> quarter_end
            # ------------------------------------------------

            mukha_start, mukha_quarter_end = quarters[mukha_quarter]

            mukha_end = mukha_start + duration / 6

            puccha_quarter_start, puccha_end = quarters[puccha_quarter]

            puccha_start = puccha_end - duration / 10

            # ------------------------------------------------
            # Sanity checks.
            # ------------------------------------------------

            if not (
                start <= mukha_start < mukha_end <= end
            ):
                raise ValueError(
                    f"Invalid Mukha interval:\n"
                    f"{start_local} -> {end_local}\n"
                    f"Mukha: {mukha_start} -> {mukha_end}"
                )

            if not (
                start <= puccha_start < puccha_end <= end
            ):
                raise ValueError(
                    f"Invalid Puccha interval:\n"
                    f"{start_local} -> {end_local}\n"
                    f"Puccha: {puccha_start} -> {puccha_end}"
                )

            # ------------------------------------------------
            # Construct a non-overlapping partition:
            #
            #   Bhadra_Mukha
            #   Bhadra
            #   Bhadra_Puccha
            #
            # This is important because your table has a
            # primary key on Start_Date_Time_UTC.
            # ------------------------------------------------

            segments = []

            # Collect all boundary points.
            boundaries = {
                start,
                end,
                mukha_start,
                mukha_end,
                puccha_start,
                puccha_end,
            }

            boundaries = sorted(boundaries)

            # Remove duplicate boundaries while retaining
            # chronological order.
            unique_boundaries = []

            for dt in boundaries:
                if not unique_boundaries or dt != unique_boundaries[-1]:
                    unique_boundaries.append(dt)

            # ------------------------------------------------
            # Classify each small interval.
            # ------------------------------------------------

            for seg_start, seg_end in zip(
                unique_boundaries[:-1],
                unique_boundaries[1:],
            ):

                midpoint = seg_start + (seg_end - seg_start) / 2

                if mukha_start <= midpoint < mukha_end:
                    bhadra_type = "Bhadra_Mukha"

                elif puccha_start <= midpoint < puccha_end:
                    bhadra_type = "Bhadra_Puccha"

                else:
                    bhadra_type = "Bhadra"

                # Convert local to UTC.
                seg_start_utc = seg_start.astimezone(ZoneInfo("UTC"))
                seg_end_utc = seg_end.astimezone(ZoneInfo("UTC"))

                insert_rows.append(
                    (
                        format_datetime(seg_start_utc),
                        format_datetime(seg_end_utc),
                        format_datetime(seg_start),
                        format_datetime(seg_end),
                        LOCATION,
                        LATITUDE,
                        LONGITUDE,
                        bhadra_type,
                    )
                )

        # ----------------------------------------------------
        # Insert.
        # ----------------------------------------------------

        conn.executemany(
            """
            INSERT INTO Bhadra_Transition (
                Start_Date_Time_UTC,
                End_Date_Time_UTC,
                Start_Date_Time_Local,
                End_Date_Time_Local,
                Location,
                Latitude,
                Longitude,
                Bhadra_Type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            insert_rows,
        )

        conn.commit()

        print(
            f"Inserted {len(insert_rows):,} "
            f"Bhadra transition rows."
        )

        # ----------------------------------------------------
        # Validation.
        # ----------------------------------------------------

        counts = conn.execute(
            """
            SELECT
                Bhadra_Type,
                COUNT(*)
            FROM Bhadra_Transition
            WHERE Location = ?
              AND Start_Date_Time_Local >= ?
              AND Start_Date_Time_Local < ?
            GROUP BY Bhadra_Type
            ORDER BY Bhadra_Type
            """,
            (
                LOCATION,
                START_DATE,
                END_DATE,
            ),
        ).fetchall()

        print("\nRows by Bhadra type:")

        for bhadra_type, count in counts:
            print(f"  {bhadra_type:16s} {count:,}")

    finally:
        conn.close()


if __name__ == "__main__":
    populate_bhadra_transition()
