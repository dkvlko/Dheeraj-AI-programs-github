import math
import os
import sqlite3
from datetime import datetime
from flask import render_template, request
from pathlib import Path
from . import dailylog_bp


# Change this environment variable if activities.db is stored elsewhere.
ACTIVITY_DB_PATH = Path(
        "/data/BLOBS/SandasServ_BLOB/activities.db"
)

PAGE_SIZE = 100

# Columns that are common to every activity table and should appear first.
STANDARD_COLUMNS = [
    "activity_time",
    "location",
    "latitude",
    "longitude",
    "location_source",
]

# Columns which are normally useful internally but should not be shown
# as activity information.
HIDDEN_COLUMNS = {
    "id",
    "created_at",
}


def get_db_connection():
    conn = sqlite3.connect(ACTIVITY_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_activity_tables(conn):
    """
    Return only tables whose names end with the literal suffix '_activity'.
    """
    rows = conn.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name LIKE '%\\_activity' ESCAPE '\\'
        ORDER BY name
    """).fetchall()

    return [row["name"] for row in rows]


def get_table_columns(conn, table_name):
    """
    Get column names for one activity table.
    Table names come from sqlite_master, not directly from the user.
    """
    rows = conn.execute(
        f'PRAGMA table_info("{table_name.replace(chr(34), chr(34) + chr(34))}")'
    ).fetchall()

    return [row["name"] for row in rows]


def quote_identifier(identifier):
    """Safely quote a SQLite identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def get_activity_rows(conn, table_name, columns):
    """
    Read all rows from one activity table.

    The returned records contain:
        table_name
        activity_name
        activity_time
        created_at
        values
    """
    quoted_table = quote_identifier(table_name)

    rows = conn.execute(
        f"SELECT * FROM {quoted_table}"
    ).fetchall()

    result = []

    for row in rows:
        data = dict(row)

        # created_at is used for sorting the combined activity stream.
        # Fall back to activity_time when created_at is absent.
        created_at = data.get("created_at")
        activity_time = data.get("activity_time")

        result.append({
            "table_name": table_name,
            "activity_name": table_name[:-9],  # remove "_activity"
            "activity_time": activity_time,
            "created_at": created_at or activity_time or "",
            "values": data,
            "columns": columns,
        })

    return result


def sort_key(item):
    """
    SQLite stores our timestamps as YYYY-MM-DD HH:MM:SS, so lexical
    sorting gives chronological sorting. Invalid/missing dates go last.
    """
    value = item.get("created_at") or ""

    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return datetime.min


@dailylog_bp.route("/")
def recent_activities():
    page = request.args.get("page", 1, type=int)
    page = max(page, 1)

    # Activity selected from the filter.
    selected_activity = request.args.get("activity", "").strip()

    conn = get_db_connection()

    try:
        # Get all valid activity tables.
        activity_tables = get_activity_tables(conn)

        # Validate the requested activity table.
        # Never use an arbitrary URL parameter directly as a table name.
        if selected_activity and selected_activity not in activity_tables:
            selected_activity = ""

        # If an activity was selected, only process that table.
        if selected_activity:
            tables = [selected_activity]
        else:
            tables = activity_tables

        all_activities = []

        for table_name in tables:
            columns = get_table_columns(conn, table_name)

            if not columns:
                continue

            all_activities.extend(
                get_activity_rows(
                    conn,
                    table_name,
                    columns
                )
            )

    finally:
        conn.close()

    # Most recently created/entered activity first.
    all_activities.sort(
        key=sort_key,
        reverse=True
    )

    total = len(all_activities)

    total_pages = max(
        1,
        math.ceil(total / PAGE_SIZE)
    )

    if page > total_pages:
        page = total_pages

    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE

    activities = all_activities[start:end]

    return render_template(
        "recent_activities.html",

        activities=activities,

        page=page,
        total_pages=total_pages,
        total=total,
        page_size=PAGE_SIZE,

        # Needed by the activity filter.
        activity_tables=activity_tables,
        selected_activity=selected_activity,

        standard_columns=STANDARD_COLUMNS,
        hidden_columns=HIDDEN_COLUMNS,
    )
