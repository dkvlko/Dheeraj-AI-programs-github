#!/usr/bin/env python3

"""
Generate a JSON file containing today's events and the following
6 days (7 calendar days total).

Output:
    /home/dkvlko/Dheeraj-AI-programs-github/liv_code/
    SandasUrineServer/app/modules/newsanddays/data/
    sortedeventstoday.json

Database:
    /data/BLOBS/CalAndHolidays/CalAndHolidays.db

Date/time:
    Asia/Kolkata

Rules:
    - Today is always the first date in the JSON.
    - Seven calendar days are included: today + next 6 days.
    - If today has no Holiday_Event_Occurrences entry:
          "No Events Today"
    - Sunday:
          "Public Holiday"
    - Wednesday:
          "Munshipuliya Closed and Mahangar has open Market"

Holiday descriptions come from:
    Holiday_Event_Definitions.Description

Occurrence information comes from:
    Holiday_Event_Occurrences

Effect information is read from:
    Holiday_Event_Effects

The Holiday_Event_Effects table is inspected dynamically so that
this program does not depend on one particular effect-column name.
"""


from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


# ============================================================
# Configuration
# ============================================================

DB_PATH = Path(
    "/data/BLOBS/CalAndHolidays/CalAndHolidays.db"
)

OUTPUT_PATH = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/"
    "liv_code/SandasUrineServer/app/modules/newsanddays/data/"
    "sortedeventstoday.json"
)

TIME_ZONE = ZoneInfo("Asia/Kolkata")

NUMBER_OF_DAYS = 7


# ============================================================
# SQLite helpers
# ============================================================

def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check whether a table exists."""

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


def get_columns(
    conn: sqlite3.Connection,
    table_name: str,
) -> list[str]:
    """Return column names for a table."""

    if not table_exists(conn, table_name):
        return []

    rows = conn.execute(
        f'PRAGMA table_info("{table_name.replace(chr(34), chr(34) * 2)}")'
    ).fetchall()

    return [row[1] for row in rows]


def quote_identifier(identifier: str) -> str:
    """Safely quote a SQLite identifier."""

    return '"' + identifier.replace('"', '""') + '"'


# ============================================================
# Effect handling
# ============================================================

def find_effect_records(
    conn: sqlite3.Connection,
    event_id: int,
) -> list[dict]:
    """
    Read effect information from Holiday_Event_Effects.

    Because the exact effect-column names may evolve, this routine
    discovers the table columns dynamically.

    Event_ID is used when available.

    All useful non-ID values are returned.
    """

    table_name = "Holiday_Event_Effects"

    if not table_exists(conn, table_name):
        return []

    columns = get_columns(conn, table_name)

    if not columns:
        return []

    # --------------------------------------------------------
    # Find Event_ID column.
    # --------------------------------------------------------

    event_id_column = None

    for column in columns:
        if column.lower() == "event_id":
            event_id_column = column
            break

    if event_id_column is None:
        return []

    # --------------------------------------------------------
    # Find Is_Active if present.
    # --------------------------------------------------------

    active_column = None

    for column in columns:
        if column.lower() == "is_active":
            active_column = column
            break

    select_columns = [
        quote_identifier(column)
        for column in columns
    ]

    sql = (
        "SELECT "
        + ", ".join(select_columns)
        + f" FROM {quote_identifier(table_name)}"
        + f" WHERE {quote_identifier(event_id_column)} = ?"
    )

    parameters = [event_id]

    if active_column is not None:
        sql += (
            f" AND {quote_identifier(active_column)} = 1"
        )

    rows = conn.execute(sql, parameters).fetchall()

    effects = []

    # --------------------------------------------------------
    # Columns which are normally internal rather than
    # descriptive.
    # --------------------------------------------------------

    internal_names = {
        "event_effect_id",
        "event_id",
        "is_active",
        "created_date",
        "modified_date",
    }

    for row in rows:

        effect = {}

        for index, column in enumerate(columns):

            value = row[index]

            if value is None:
                continue

            if column.lower() in internal_names:
                continue

            # Ignore empty strings.
            if isinstance(value, str) and not value.strip():
                continue

            effect[column] = value

        if effect:
            effects.append(effect)

    return effects


# ============================================================
# Holiday event retrieval
# ============================================================

def get_holiday_events(
    conn: sqlite3.Connection,
    start_date: date,
    end_date: date,
) -> dict[str, list[dict]]:
    """
    Retrieve Holiday_Event_Occurrences in the requested date range.

    Returns:

        {
            "2026-09-17": [...],
            "2026-09-18": [...],
            ...
        }
    """

    result = {}

    rows = conn.execute(
        """
        SELECT
            o.Event_ID,
            o.Event_Year,
            o.Event_Date,
            o.Date_Status,
            o.Date_Calculation_Method,
            o.Is_Confirmed,
            o.Notes,

            d.Event_Name,
            d.Event_Type,
            d.Description,
            d.Is_Active

        FROM Holiday_Event_Occurrences o

        JOIN Holiday_Event_Definitions d
          ON d.Event_ID = o.Event_ID

        WHERE o.Event_Date BETWEEN ? AND ?
          AND d.Is_Active = 1

        ORDER BY
            o.Event_Date,
            d.Event_Name
        """,
        (
            start_date.isoformat(),
            end_date.isoformat(),
        ),
    ).fetchall()

    for row in rows:

        event_date = row["Event_Date"]

        effects = find_effect_records(
            conn,
            row["Event_ID"],
        )

        event = {
            "event_id": row["Event_ID"],
            "event_name": row["Event_Name"],
            "event_type": row["Event_Type"],
            "description": row["Description"],
            "date_status": row["Date_Status"],
            "date_calculation_method": (
                row["Date_Calculation_Method"]
            ),
            "is_confirmed": bool(row["Is_Confirmed"]),
            "notes": row["Notes"],
            "effects": effects,
        }

        result.setdefault(
            event_date,
            [],
        ).append(event)

    return result


# ============================================================
# Daily special rules
# ============================================================

def get_special_daily_events(
    current_date: date,
) -> list[dict]:
    """
    Generate the special day-of-week events requested by the user.
    """

    events = []

    # Python:
    # Monday    = 0
    # Tuesday   = 1
    # Wednesday = 2
    # Thursday  = 3
    # Friday    = 4
    # Saturday  = 5
    # Sunday    = 6

    weekday = current_date.weekday()

    # --------------------------------------------------------
    # Sunday
    # --------------------------------------------------------

    if weekday == 6:

        events.append(
            {
                "event_id": None,
                "event_name": "Public Holiday",
                "event_type": "WEEKLY_RULE",
                "description": (
                    "Sunday is treated as a Public Holiday."
                ),
                "date_status": "RULE",
                "date_calculation_method": (
                    "WEEKLY_DAY_OF_WEEK"
                ),
                "is_confirmed": True,
                "notes": None,
                "effects": [
                    {
                        "effect_type": "PUBLIC_LIFE",
                        "effect": "Public Holiday",
                    }
                ],
            }
        )

    # --------------------------------------------------------
    # Wednesday
    # --------------------------------------------------------

    if weekday == 2:

        events.append(
            {
                "event_id": None,
                "event_name": (
                    "Munshipuliya Closed and Mahangar "
                    "has open Market"
                ),
                "event_type": "WEEKLY_RULE",
                "description": (
                    "Wednesday weekly market arrangement."
                ),
                "date_status": "RULE",
                "date_calculation_method": (
                    "WEEKLY_DAY_OF_WEEK"
                ),
                "is_confirmed": True,
                "notes": None,
                "effects": [
                    {
                        "effect_type": "LOCAL_LIFE",
                        "effect": (
                            "Munshipuliya Closed and "
                            "Mahangar has open Market"
                        ),
                    }
                ],
            }
        )

    if weekday == 5:

        events.append(
            {
                "event_id": None,
                "event_name": (
                    "Sensex Closed"
                ),
                "event_type": "WEEKLY_RULE",
                "description": (
                    "Sensex is closed on Saturdays."
                ),
                "date_status": "RULE",
                "date_calculation_method": (
                    "WEEKLY_DAY_OF_WEEK"
                ),
                "is_confirmed": True,
                "notes": None,
                "effects": [
                    {
                        "effect_type": "PUBLIC_LIFE",
                        "effect": (
                            "Sensex Closed."
                        ),
                    }
                ],
            }
        )

    return events


# ============================================================
# Build JSON
# ============================================================

def build_json(
    conn: sqlite3.Connection,
    today: date,
) -> dict:
    """
    Build the complete seven-day JSON document.
    """

    end_date = (
        today
        + timedelta(days=NUMBER_OF_DAYS - 1)
    )

    holiday_events = get_holiday_events(
        conn,
        today,
        end_date,
    )

    days = []

    for offset in range(NUMBER_OF_DAYS):

        current_date = today + timedelta(days=offset)

        date_text = current_date.isoformat()

        weekday_name = current_date.strftime("%A")

        events = []

        # ----------------------------------------------------
        # Database holiday events.
        # ----------------------------------------------------

        events.extend(
            holiday_events.get(
                date_text,
                [],
            )
        )

        # ----------------------------------------------------
        # Weekly/special rules.
        #
        # These are deliberately added after the database
        # events so actual holiday events remain primary.
        # ----------------------------------------------------

        events.extend(
            get_special_daily_events(
                current_date
            )
        )

        # ----------------------------------------------------
        # Special handling for TODAY.
        #
        # If there are no events at all today, explicitly
        # generate "No Events Today".
        # ----------------------------------------------------

        if offset == 0 and not events:

            events.append(
                {
                    "event_id": None,
                    "event_name": "No Events Today",
                    "event_type": "NO_EVENT",
                    "description": (
                        "No holiday or registered event "
                        "was found for today."
                    ),
                    "date_status": "INFORMATIONAL",
                    "date_calculation_method": None,
                    "is_confirmed": True,
                    "notes": None,
                    "effects": [],
                }
            )

        days.append(
            {
                "date": date_text,
                "day": weekday_name,
                "is_today": offset == 0,
                "events": events,
            }
        )

    return {
        "generated_at": (
            __import__("datetime")
            .datetime.now(TIME_ZONE)
            .isoformat()
        ),
        "timezone": "Asia/Kolkata",
        "start_date": today.isoformat(),
        "end_date": end_date.isoformat(),
        "number_of_days": NUMBER_OF_DAYS,
        "days": days,
    }

# Generate today's Events #

def generateEvents() :

    if not DB_PATH.exists():

        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    # --------------------------------------------------------
    # Ensure output directory exists.
    # --------------------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Determine TODAY using India local time.
    # --------------------------------------------------------

    now = __import__("datetime").datetime.now(
        TIME_ZONE
    )

    today = now.date()

    #print(
    #    f"Generating events from "
    #    f"{today.isoformat()} "
    #    f"for {NUMBER_OF_DAYS} days."
    #)

    # --------------------------------------------------------
    # SQLite connection.
    # --------------------------------------------------------

    conn = sqlite3.connect(
        str(DB_PATH)
    )

    conn.row_factory = sqlite3.Row

    try:

        document = build_json(
            conn,
            today,
        )

    finally:

        conn.close()

    # --------------------------------------------------------
    # Write JSON.
    # --------------------------------------------------------

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as json_file:

        json.dump(
            document,
            json_file,
            ensure_ascii=False,
            indent=4,
        )

        json_file.write("\n")

    #print()
    #print(
    #    f"JSON written to:\n{OUTPUT_PATH}"
    #)

    #print(
    #    f"Date range: "
    #    f"{document['start_date']} "
    #    f"to "
    #    f"{document['end_date']}"
    #)

# ============================================================
# Main
# ============================================================

def main() -> None:
    generateEvents()


if __name__ == "__main__":
    main()
