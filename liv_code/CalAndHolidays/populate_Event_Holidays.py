#!/usr/bin/env python3

"""
Populate Holiday_Event_Occurrences from registered holiday event sources.

Database:
    /data/BLOBS/CalAndHolidays/CalAndHolidays.db

Initial population range:
    2026 - 2027

Architecture:
    Holiday_Event_Definitions
            |
            v
    Holiday_Event_Date_Sources
            |
            v
    Database_DateTime_Column_Definitions
            |
            v
    Source Holiday Tables
            |
            v
    Holiday_Event_Occurrences

The program also inserts the six fixed Sensex holidays:

    New Year's Day
    Republic Day
    Dr. Baba Saheb Ambedkar Jayanti
    Maharashtra Day
    Mahatma Gandhi Jayanti
    Christmas

The program is intentionally metadata-driven for precalculated
holiday tables. No holiday-specific calculation code is used for
the 21 registered precalculated event sources.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional


# ============================================================
# Configuration
# ============================================================

DB_PATH = Path("/data/BLOBS/CalAndHolidays/CalAndHolidays.db")

START_YEAR = 2026
END_YEAR = 2027


# ============================================================
# Fixed Gregorian holidays
# ============================================================

FIXED_GREGORIAN_HOLIDAYS = {
    "New Year's Day": (1, 1),
    "Republic Day": (1, 26),
    "Dr. Baba Saheb Ambedkar Jayanti": (4, 14),
    "Maharashtra Day": (5, 1),
    "Mahatma Gandhi Jayanti": (10, 2),
    "Christmas": (12, 25),
}


# ============================================================
# Utility functions
# ============================================================

def quote_identifier(identifier: str) -> str:
    """
    Safely quote a SQLite identifier.

    Table names and column names cannot be supplied as normal
    SQL parameters, so they must be validated/quoted separately.
    """
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("Invalid SQLite identifier")

    return '"' + identifier.replace('"', '""') + '"'


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Return True if a SQLite table exists."""
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def column_exists(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    """Return True if a column exists in a SQLite table."""
    if not table_exists(conn, table_name):
        return False

    rows = conn.execute(
        f"PRAGMA table_info({quote_identifier(table_name)})"
    ).fetchall()

    return any(row["name"] == column_name for row in rows)


def normalize_date_value(value) -> Optional[date]:
    """
    Convert a source date value to datetime.date.

    Expected canonical database date format:
        YYYY-MM-DD

    Some source tables may contain datetime strings. Those are
    also handled so that the date portion can be extracted safely.
    """

    if value is None:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()

    if not text:
        return None

    # --------------------------------------------------------
    # Canonical DATE
    # --------------------------------------------------------
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass

    # --------------------------------------------------------
    # ISO datetime
    # --------------------------------------------------------
    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        ).date()
    except ValueError:
        pass

    # --------------------------------------------------------
    # Common alternative date formats
    # --------------------------------------------------------
    formats = (
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    )

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    raise ValueError(
        f"Unable to interpret date value: {value!r}"
    )


def get_date_metadata(
    conn: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> Optional[sqlite3.Row]:
    """
    Get date/time metadata for a particular table/column.
    """
    return conn.execute(
        """
        SELECT
            DateTime_Column_ID,
            Table_Name,
            Column_Name,
            Value_Type,
            Storage_Type,
            Storage_Format,
            Timezone_Name,
            Is_Date_Only,
            Is_Time_Only,
            Description,
            Is_Active
        FROM Database_DateTime_Column_Definitions
        WHERE Table_Name = ?
          AND Column_Name = ?
          AND Is_Active = 1
        """,
        (table_name, column_name),
    ).fetchone()


def get_event_id(
    conn: sqlite3.Connection,
    event_name: str,
) -> Optional[int]:
    """Return Event_ID for an event name."""
    row = conn.execute(
        """
        SELECT Event_ID
        FROM Holiday_Event_Definitions
        WHERE Event_Name = ?
          AND Is_Active = 1
        """,
        (event_name,),
    ).fetchone()

    return row["Event_ID"] if row else None


def occurrence_exists(
    conn: sqlite3.Connection,
    event_id: int,
    event_date: str,
) -> bool:
    """Check whether the occurrence already exists."""
    row = conn.execute(
        """
        SELECT 1
        FROM Holiday_Event_Occurrences
        WHERE Event_ID = ?
          AND Event_Date = ?
        LIMIT 1
        """,
        (event_id, event_date),
    ).fetchone()

    return row is not None


def insert_occurrence(
    conn: sqlite3.Connection,
    *,
    event_id: int,
    event_year: int,
    event_date: str,
    date_status: str,
    calculation_method: str,
    is_confirmed: int,
    notes: str,
) -> bool:
    """
    Insert one occurrence.

    Returns:
        True  = inserted
        False = already existed
    """

    if occurrence_exists(
        conn,
        event_id,
        event_date,
    ):
        return False

    conn.execute(
        """
        INSERT INTO Holiday_Event_Occurrences
        (
            Event_ID,
            Event_Year,
            Event_Date,
            Date_Status,
            Date_Calculation_Method,
            Is_Confirmed,
            Notes
        )
        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            event_id,
            event_year,
            event_date,
            date_status,
            calculation_method,
            is_confirmed,
            notes,
        ),
    )

    return True


# ============================================================
# Populate fixed Gregorian holidays
# ============================================================

def populate_fixed_holidays(
    conn: sqlite3.Connection,
) -> tuple[int, int]:

    inserted = 0
    skipped = 0

    print()
    print("=" * 70)
    print("FIXED GREGORIAN HOLIDAYS")
    print("=" * 70)

    for event_name, (month, day) in FIXED_GREGORIAN_HOLIDAYS.items():

        event_id = get_event_id(conn, event_name)

        if event_id is None:
            raise RuntimeError(
                f"Holiday event definition not found: {event_name}"
            )

        for year in range(START_YEAR, END_YEAR + 1):

            event_date = date(year, month, day)

            inserted_now = insert_occurrence(
                conn,
                event_id=event_id,
                event_year=year,
                event_date=event_date.isoformat(),
                date_status="KNOWN",
                calculation_method="FIXED_GREGORIAN_DATE",
                is_confirmed=1,
                notes="Fixed Gregorian Sensex holiday",
            )

            if inserted_now:
                inserted += 1

                print(
                    f"INSERT  {year}  "
                    f"{event_date.isoformat()}  "
                    f"{event_name}"
                )
            else:
                skipped += 1

                print(
                    f"SKIP    {year}  "
                    f"{event_date.isoformat()}  "
                    f"{event_name} "
                    f"(already exists)"
                )

    return inserted, skipped


# ============================================================
# Populate precalculated event sources
# ============================================================

def populate_precalculated_sources(
    conn: sqlite3.Connection,
) -> tuple[int, int, int]:
    """
    Populate Holiday_Event_Occurrences from all active
    Holiday_Event_Date_Sources mappings.

    Returns:
        inserted
        skipped
        ignored_outside_year_range
    """

    inserted = 0
    skipped = 0
    ignored_outside_year_range = 0

    print()
    print("=" * 70)
    print("PRECALCULATED HOLIDAY SOURCES")
    print("=" * 70)

    mappings = conn.execute(
        """
        SELECT
            s.Event_Date_Source_ID,
            s.Event_ID,
            d.Event_Name,
            s.Source_Table_Name,
            s.Source_Date_Column_Name,
            s.Source_Event_Column_Name,
            s.Source_Year_Column_Name,
            s.Source_Filter_Expression,
            s.Source_Type,
            s.Description
        FROM Holiday_Event_Date_Sources s
        JOIN Holiday_Event_Definitions d
          ON d.Event_ID = s.Event_ID
        WHERE s.Is_Active = 1
          AND d.Is_Active = 1
        ORDER BY
            s.Event_Date_Source_ID
        """
    ).fetchall()

    if not mappings:
        print("No active Holiday_Event_Date_Sources found.")
        return 0, 0, 0

    print(f"Active source mappings: {len(mappings)}")
    print()

    for mapping in mappings:

        source_id = mapping["Event_Date_Source_ID"]
        event_id = mapping["Event_ID"]
        event_name = mapping["Event_Name"]
        source_table = mapping["Source_Table_Name"]
        source_date_column = mapping["Source_Date_Column_Name"]
        source_year_column = mapping["Source_Year_Column_Name"]
        source_filter = mapping["Source_Filter_Expression"]
        source_type = mapping["Source_Type"]
        description = mapping["Description"]

        print("-" * 70)
        print(
            f"Source ID       : {source_id}\n"
            f"Event           : {event_name}\n"
            f"Source table    : {source_table}\n"
            f"Date column     : {source_date_column}\n"
            f"Source type     : {source_type}"
        )

        # ----------------------------------------------------
        # Source table must exist.
        # ----------------------------------------------------
        if not table_exists(conn, source_table):
            print(
                f"WARNING: source table does not exist: "
                f"{source_table}"
            )
            continue

        # ----------------------------------------------------
        # Source date column must exist.
        # ----------------------------------------------------
        if not column_exists(
            conn,
            source_table,
            source_date_column,
        ):
            print(
                f"WARNING: source date column does not exist: "
                f"{source_table}.{source_date_column}"
            )
            continue

        # ----------------------------------------------------
        # Date metadata must exist.
        # ----------------------------------------------------
        metadata = get_date_metadata(
            conn,
            source_table,
            source_date_column,
        )

        if metadata is None:
            print(
                "WARNING: no active date metadata found for "
                f"{source_table}.{source_date_column}"
            )
            continue

        value_type = metadata["Value_Type"]

        print(f"Value type      : {value_type}")

        # ----------------------------------------------------
        # This program currently expects a date-bearing column.
        # ----------------------------------------------------
        if value_type not in (
            "DATE",
            "DATETIME_UTC",
            "DATETIME_LOCAL",
        ):
            print(
                f"WARNING: unsupported source Value_Type "
                f"{value_type!r} for "
                f"{source_table}.{source_date_column}"
            )
            continue

        # ----------------------------------------------------
        # Construct SELECT safely.
        # ----------------------------------------------------
        quoted_table = quote_identifier(source_table)
        quoted_date_column = quote_identifier(
            source_date_column
        )

        select_sql = (
            f"SELECT rowid AS _source_rowid, "
            f"{quoted_date_column} AS _event_date "
            f"FROM {quoted_table}"
        )

        # ----------------------------------------------------
        # Optional source filter.
        #
        # NOTE:
        # Source_Filter_Expression is trusted metadata
        # maintained by the database owner. It is therefore
        # inserted as SQL rather than passed as a parameter.
        # ----------------------------------------------------
        if source_filter:
            select_sql += f" WHERE ({source_filter})"

        try:
            source_rows = conn.execute(select_sql).fetchall()
        except sqlite3.Error as exc:
            print(
                "WARNING: unable to read source table "
                f"{source_table}: {exc}"
            )
            continue

        print(f"Source rows     : {len(source_rows)}")

        source_inserted = 0
        source_skipped = 0

        for source_row in source_rows:

            raw_date = source_row["_event_date"]

            if raw_date is None:
                continue

            try:
                event_date_obj = normalize_date_value(
                    raw_date
                )
            except ValueError as exc:
                print(
                    f"WARNING: invalid date in "
                    f"{source_table}.{source_date_column}: "
                    f"{raw_date!r} ({exc})"
                )
                continue

            if event_date_obj is None:
                continue

            event_year = event_date_obj.year

            # ------------------------------------------------
            # Only populate requested years.
            # ------------------------------------------------
            if not (
                START_YEAR
                <= event_year
                <= END_YEAR
            ):
                ignored_outside_year_range += 1
                continue

            event_date_text = event_date_obj.isoformat()

            notes = (
                f"{description or 'Precalculated holiday date'}; "
                f"Source: {source_table}.{source_date_column}; "
                f"Source ID: {source_id}"
            )

            inserted_now = insert_occurrence(
                conn,
                event_id=event_id,
                event_year=event_year,
                event_date=event_date_text,
                date_status="KNOWN",
                calculation_method="PRECALCULATED",
                is_confirmed=1,
                notes=notes,
            )

            if inserted_now:
                inserted += 1
                source_inserted += 1

                print(
                    f"INSERT  {event_date_text}  "
                    f"{event_name}"
                )

            else:
                skipped += 1
                source_skipped += 1

        print(
            f"Result          : "
            f"{source_inserted} inserted, "
            f"{source_skipped} already existed"
        )

    return (
        inserted,
        skipped,
        ignored_outside_year_range,
    )


# ============================================================
# Validation
# ============================================================

def validate_database(conn: sqlite3.Connection) -> None:
    """
    Validate that the tables required by this program exist.
    """

    required_tables = (
        "Holiday_Event_Definitions",
        "Holiday_Event_Date_Sources",
        "Holiday_Event_Occurrences",
        "Database_DateTime_Column_Definitions",
    )

    print()
    print("=" * 70)
    print("DATABASE VALIDATION")
    print("=" * 70)

    for table in required_tables:

        if not table_exists(conn, table):
            raise RuntimeError(
                f"Required table does not exist: {table}"
            )

        print(f"OK      {table}")


# ============================================================
# Final report
# ============================================================

def print_final_report(conn: sqlite3.Connection) -> None:

    print()
    print("=" * 70)
    print("FINAL OCCURRENCE REPORT")
    print("=" * 70)

    rows = conn.execute(
        """
        SELECT
            o.Event_Year,
            o.Event_Date,
            d.Event_Name,
            o.Date_Status,
            o.Date_Calculation_Method,
            o.Is_Confirmed
        FROM Holiday_Event_Occurrences o
        JOIN Holiday_Event_Definitions d
          ON d.Event_ID = o.Event_ID
        WHERE o.Event_Year BETWEEN ? AND ?
        ORDER BY
            o.Event_Date,
            d.Event_Name
        """,
        (START_YEAR, END_YEAR),
    ).fetchall()

    print(
        f"Occurrences for {START_YEAR}-{END_YEAR}: "
        f"{len(rows)}"
    )

    print()

    for row in rows:
        print(
            f"{row['Event_Year']} | "
            f"{row['Event_Date']} | "
            f"{row['Event_Name']} | "
            f"{row['Date_Status']} | "
            f"{row['Date_Calculation_Method']} | "
            f"{row['Is_Confirmed']}"
        )


# ============================================================
# Main
# ============================================================

def main() -> None:

    print("=" * 70)
    print("HOLIDAY EVENT OCCURRENCE POPULATOR")
    print("=" * 70)
    print(f"Database        : {DB_PATH}")
    print(f"Start year      : {START_YEAR}")
    print(f"End year        : {END_YEAR}")
    print()

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    conn = sqlite3.connect(str(DB_PATH))

    # Return rows by column name.
    conn.row_factory = sqlite3.Row

    try:

        validate_database(conn)

        # ----------------------------------------------------
        # Begin one transaction for the entire population.
        # ----------------------------------------------------
        conn.execute("BEGIN")

        fixed_inserted, fixed_skipped = (
            populate_fixed_holidays(conn)
        )

        (
            calculated_inserted,
            calculated_skipped,
            ignored_outside_range,
        ) = populate_precalculated_sources(conn)

        conn.commit()

        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------
        print()
        print("=" * 70)
        print("POPULATION COMPLETE")
        print("=" * 70)

        print(
            f"Fixed holidays inserted       : "
            f"{fixed_inserted}"
        )

        print(
            f"Fixed holidays already exist  : "
            f"{fixed_skipped}"
        )

        print(
            f"Precalculated inserted        : "
            f"{calculated_inserted}"
        )

        print(
            f"Precalculated already exist   : "
            f"{calculated_skipped}"
        )

        print(
            f"Outside requested year range  : "
            f"{ignored_outside_range}"
        )

        print()

        print_final_report(conn)

    except Exception:

        # ----------------------------------------------------
        # Roll back everything if anything unexpected occurs.
        # ----------------------------------------------------
        conn.rollback()

        print()
        print("=" * 70)
        print("ERROR: TRANSACTION ROLLED BACK")
        print("=" * 70)

        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
