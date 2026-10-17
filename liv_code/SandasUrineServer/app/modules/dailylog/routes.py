import math
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from flask import (
    render_template,
    request,
    redirect,
    url_for,
)

from . import dailylog_bp

IST = ZoneInfo("Asia/Kolkata")

# Change this environment variable if activities.db is stored elsewhere.
ACTIVITY_DB_PATH = Path(
        "/data/BLOBS/SandasServ_BLOB/activities.db"
)

PAGE_SIZE = 100

# Columns that are common to every activity table and should appear first.
STANDARD_COLUMNS = [
    "start_time",
    "start_location",
    "start_latitude",
    "start_longitude",
    "start_location_source",
    "finish_time",
    "finish_location",
    "finish_latitude",
    "finish_longitude",
    "finish_location_source",
    "status",
]

# Columns which are normally useful internally but should not be shown
# as activity information.
HIDDEN_COLUMNS = {
    "id",
    "history_id",
    "created_at",
}

def parse_datetime(value):
    """
    Convert HTML datetime-local value into the
    YYYY-MM-DD HH:MM:SS format used by SQLite.
    """

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%dT%H:%M"
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    except ValueError:
        return None

def get_created_at():
    """
    Return the current application creation timestamp in IST.
    Stored as YYYY-MM-DD HH:MM:SS for SQLite.
    """
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

def get_db_connection():
    conn = sqlite3.connect(ACTIVITY_DB_PATH)
    conn.row_factory = sqlite3.Row

    # Enforce FOREIGN KEY constraints.
    conn.execute("PRAGMA foreign_keys = ON")
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



def quote_identifier(identifier):
    """Safely quote a SQLite identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def activity_display_name(table_name):
    """
    Convert:
        Reading_activity
    into:
        Reading
    """

    if table_name.endswith("_activity"):
        return table_name[:-9]

    return table_name

def get_table_columns(conn, table_name):
    """
    Return column names for an activity table.
    """

    quoted_table = quote_identifier(table_name)

    rows = conn.execute(
        f"PRAGMA table_info({quoted_table})"
    ).fetchall()

    return [row["name"] for row in rows]

def get_activity_rows(conn, table_name, columns):
    """
    Return activity records combined with their corresponding
    activity_history records.

    activity_history is the authoritative source for:
        start time
        start location
        finish time
        finish location
        status

    The activity-specific table supplies the remaining fields.
    """

    quoted_table = quote_identifier(table_name)

    rows = conn.execute(
        f"""
        SELECT
            h.id AS history_id,
            h.activity_table,

            h.start_time,
            h.start_location,
            h.start_latitude,
            h.start_longitude,
            h.start_location_source,

            h.finish_time,
            h.finish_location,
            h.finish_latitude,
            h.finish_longitude,
            h.finish_location_source,

            h.status,
            h.created_at AS history_created_at,

            a.*
            
        FROM activity_history AS h

        LEFT JOIN {quoted_table} AS a
            ON a.history_id = h.id

        WHERE h.activity_table = ?

        ORDER BY h.start_time DESC
        """,
        (table_name,)
    ).fetchall()

    result = []

    for row in rows:

        data = dict(row)

        # The activity table also has id and created_at.
        # Keep the history ID as the main record identifier.
        data["id"] = data.get("history_id")

        # Use the history creation time for sorting/display.
        data["created_at"] = (
            data.get("history_created_at")
            or data.get("start_time")
            or ""
        )

        result.append({
            "table_name": table_name,

            "activity_name": activity_display_name(
                table_name
            ),

            "activity_time": data.get(
                "start_time"
            ),

            "created_at": data.get(
                "created_at"
            ),

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

    page = request.args.get(
        "page",
        1,
        type=int
    )

    page = max(page, 1)

    selected_activity = request.args.get(
        "activity",
        ""
    ).strip()

    conn = get_db_connection()

    try:

        # ---------------------------------------------------------
        # Discover valid activity tables.
        # ---------------------------------------------------------

        activity_tables = get_activity_tables(conn)

        # ---------------------------------------------------------
        # Validate activity filter.
        # ---------------------------------------------------------

        if (
            selected_activity
            and selected_activity not in activity_tables
        ):
            selected_activity = ""

        if selected_activity:
            tables = [selected_activity]
        else:
            tables = activity_tables

        all_activities = []

        # ---------------------------------------------------------
        # Read activity history + activity-specific information.
        # ---------------------------------------------------------

        for table_name in tables:

            columns = get_table_columns(
                conn,
                table_name
            )

            if not columns:
                continue

            rows = get_activity_rows(
                conn,
                table_name,
                columns
            )

            for activity in rows:

                # -------------------------------------------------
                # The history ID is the unique ID displayed on
                # the Recent Activities page.
                # -------------------------------------------------

                activity["history_id"] = (
                    activity["values"].get("history_id")
                )

                # -------------------------------------------------
                # Only activity-specific columns should appear
                # when the user expands an activity.
                #
                # Do NOT include:
                #   id
                #   history_id
                #   created_at
                #
                # Historical information such as start_time,
                # finish_time, location, status etc. is deliberately
                # excluded here.
                # -------------------------------------------------

                activity["detail_columns"] = [
                    column
                    for column in columns
                    if column not in HIDDEN_COLUMNS
                ]

                all_activities.append(activity)

    finally:

        conn.close()

    # -------------------------------------------------------------
    # Sort by activity_history.created_at.
    #
    # get_activity_rows() puts history_created_at into
    # activity["created_at"].
    # -------------------------------------------------------------

    all_activities.sort(
        key=sort_key,
        reverse=True
    )

    # -------------------------------------------------------------
    # Pagination
    # -------------------------------------------------------------

    total = len(all_activities)

    total_pages = max(
        1,
        math.ceil(
            total / PAGE_SIZE
        )
    )

    if page > total_pages:
        page = total_pages

    start = (
        page - 1
    ) * PAGE_SIZE

    end = start + PAGE_SIZE

    activities = all_activities[start:end]

    # -------------------------------------------------------------
    # Render page.
    # -------------------------------------------------------------

    return render_template(
        "recent_activities.html",

        activities=activities,

        page=page,
        total_pages=total_pages,
        total=total,
        page_size=PAGE_SIZE,

        activity_tables=activity_tables,
        selected_activity=selected_activity,

        # Kept available for compatibility with other code/template
        # logic, although the new template does not display them.
        standard_columns=STANDARD_COLUMNS,
        hidden_columns=HIDDEN_COLUMNS,
    )   

@dailylog_bp.route("/new", methods=["GET", "POST"])
def new_activity():
    message = request.args.get(
        "message",
        ""
    ).strip()
    conn = get_db_connection()

    try:

        activity_tables = get_activity_tables(conn)

        # ---------------------------------------------------------
        # GET
        # ---------------------------------------------------------

        if request.method == "GET":

            selected_activity = request.args.get(
                "activity",
                ""
            ).strip()

            action = request.args.get(
                "action",
                ""
            ).strip().upper()

            # Validate activity.
            if selected_activity not in activity_tables:
                selected_activity = ""

            active_history = None

            if selected_activity:

                active_history = conn.execute(
                    """
                    SELECT *
                    FROM activity_history
                    WHERE activity_table = ?
                      AND status = 'STARTED'
                    ORDER BY start_time DESC
                    LIMIT 1
                    """,
                    (selected_activity,)
                ).fetchone()

            activity_columns = []

            if selected_activity:

                all_columns = get_table_columns(
                    conn,
                    selected_activity
                )

                # These columns belong to the generic system,
                # not to the user activity form.
                system_columns = {
                    "id",
                    "history_id",
                    "created_at",
                }

                activity_columns = [
                    column
                    for column in all_columns
                    if column not in system_columns
                ]

            return render_template(
                "new_activity.html",
                activity_tables=activity_tables,
                selected_activity=selected_activity,
                action=action,
                active_history=active_history,
                activity_columns=activity_columns,
                message=message,
            )

        # ---------------------------------------------------------
        # POST
        # ---------------------------------------------------------

        activity_table = request.form.get(
            "activity",
            ""
        ).strip()

        action = request.form.get(
            "action",
            ""
        ).strip().upper()

        # ---------------------------------------------------------
        # Validate activity table
        # ---------------------------------------------------------

        if activity_table not in activity_tables:

            return redirect(
                url_for("dailylog.new_activity",
                                  message=f"Invalid activity selected.error."
                        )
            )

        valid_actions = {
            "START",
            "FINISH",
            "CANCEL",
            "BACKLOG",
        }

        if action not in valid_actions:

            return redirect(
                url_for("dailylog.new_activity",
                                  message=f"Invalid activity action.error"
                        )
            )

        # ---------------------------------------------------------
        # START
        # ---------------------------------------------------------

        if action == "START":

            start_time = parse_datetime(
                request.form.get("start_time")
            )

            if not start_time:

                return redirect(
                    url_for(
                        "dailylog.new_activity",
                        activity=activity_table,
                        message = "Invalid start date/time" 
                    )
                )

            start_location = (
                request.form.get("start_location", "")
                .strip()
                or None
            )

            start_latitude = (
                request.form.get("start_latitude")
                or None
            )

            start_longitude = (
                request.form.get("start_longitude")
                or None
            )

            start_location_source = (
                request.form.get(
                    "start_location_source"
                )
                or None
            )

            # Convert coordinates to numbers.
            if start_latitude:
                start_latitude = float(start_latitude)

            if start_longitude:
                start_longitude = float(start_longitude)

            created_at = get_created_at()

            conn.execute(
                """
                INSERT INTO activity_history (
                    activity_table,
                    start_time,
                    start_location,
                    start_latitude,
                    start_longitude,
                    start_location_source,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'STARTED',?)
                """,
                (
                    activity_table,
                    start_time,
                    start_location,
                    start_latitude,
                    start_longitude,
                    start_location_source,
                    created_at,
                )
            )

            conn.commit()

            return redirect(
                url_for(
                    "dailylog.new_activity",
                    activity=activity_table,
                    message = f"{activity_display_name(activity_table)} started.Success.",
                )
            )

        # ---------------------------------------------------------
        # Find active history for FINISH/CANCEL
        # ---------------------------------------------------------

        if action in {"FINISH", "CANCEL"}:

            history_id = request.form.get(
                "history_id",
                type=int
            )

            if not history_id:

                return redirect(
                    url_for(
                        "dailylog.new_activity",
                        activity=activity_table,
                        message="No active activity was selected."
                    )
                )

            history = conn.execute(
                """
                SELECT *
                FROM activity_history
                WHERE id = ?
                  AND activity_table = ?
                  AND status = 'STARTED'
                """,
                (
                    history_id,
                    activity_table,
                )
            ).fetchone()

            if not history:

                return redirect(
                    url_for(
                        "dailylog.new_activity",
                        activity=activity_table,
                        message="The selected activity is no longer active. Error.",
                    )
                )

        # ---------------------------------------------------------
        # CANCEL
        # ---------------------------------------------------------

        if action == "CANCEL":

            finish_time = parse_datetime(
                request.form.get("finish_time")
            )

            if not finish_time:

                return redirect(
                    url_for(
                        "dailylog.new_activity",
                        activity=activity_table,
                        message = "Invalid cancellation date/time.Error."
                    )
                )

            finish_location = (
                request.form.get("finish_location", "")
                .strip()
                or None
            )

            finish_latitude = (
                request.form.get("finish_latitude")
                or None
            )

            finish_longitude = (
                request.form.get("finish_longitude")
                or None
            )

            finish_location_source = (
                request.form.get(
                    "finish_location_source"
                )
                or None
            )

            if finish_latitude:
                finish_latitude = float(finish_latitude)

            if finish_longitude:
                finish_longitude = float(finish_longitude)

            conn.execute(
                """
                UPDATE activity_history
                SET
                    finish_time = ?,
                    finish_location = ?,
                    finish_latitude = ?,
                    finish_longitude = ?,
                    finish_location_source = ?,
                    status = 'CANCELLED'
                WHERE id = ?
                """,
                (
                    finish_time,
                    finish_location,
                    finish_latitude,
                    finish_longitude,
                    finish_location_source,
                    history_id,
                )
            )

            conn.commit()

            return redirect(
                url_for("dailylog.new_activity",
                                  message=f"{activity_display_name(activity_table)} cancelled.Success."
                        )
            )

        # ---------------------------------------------------------
        # FINISH
        # ---------------------------------------------------------

        if action == "FINISH":

            finish_time = parse_datetime(
                request.form.get("finish_time")
            )

            if not finish_time:

                return redirect(
                    url_for(
                        "dailylog.new_activity",
                        activity=activity_table,
                        message="Invalid finish date/time.Error."
                    )
                )

            finish_location = (
                request.form.get("finish_location", "")
                .strip()
                or None
            )

            finish_latitude = (
                request.form.get("finish_latitude")
                or None
            )

            finish_longitude = (
                request.form.get("finish_longitude")
                or None
            )

            finish_location_source = (
                request.form.get(
                    "finish_location_source"
                )
                or None
            )

            if finish_latitude:
                finish_latitude = float(finish_latitude)

            if finish_longitude:
                finish_longitude = float(finish_longitude)

            # Discover activity-specific columns.
            all_columns = get_table_columns(
                conn,
                activity_table
            )

            system_columns = {
                "id",
                "history_id",
                "created_at",
            }

            activity_columns = [
                column
                for column in all_columns
                if column not in system_columns
            ]

            values = []

            for column in activity_columns:

                value = request.form.get(
                    f"field_{column}"
                )

                if value == "":
                    value = None

                values.append(value)

            # -----------------------------------------------------
            # Transaction
            # -----------------------------------------------------

            try:

                conn.execute("BEGIN")

                conn.execute(
                    """
                    UPDATE activity_history
                    SET
                        finish_time = ?,
                        finish_location = ?,
                        finish_latitude = ?,
                        finish_longitude = ?,
                        finish_location_source = ?,
                        status = 'FINISHED'
                    WHERE id = ?
                      AND status = 'STARTED'
                    """,
                    (
                        finish_time,
                        finish_location,
                        finish_latitude,
                        finish_longitude,
                        finish_location_source,
                        history_id,
                    )
                )

                quoted_table = quote_identifier(
                    activity_table
                )

                quoted_columns = [
                    quote_identifier(column)
                    for column in activity_columns
                ]

                insert_columns = [
                    quote_identifier("history_id")
                ] + quoted_columns

                placeholders = ", ".join(
                    ["?"] * len(insert_columns)
                )

                sql = f"""
                    INSERT INTO {quoted_table}
                    ({", ".join(insert_columns)})
                    VALUES ({placeholders})
                """

                conn.execute(
                    sql,
                    [history_id] + values
                )

                conn.commit()

            except Exception:

                conn.rollback()

                raise


            return redirect(
                url_for("dailylog.new_activity",
                         message = f"{activity_display_name(activity_table)} finished.Success."
                        )
            )

        # ---------------------------------------------------------
        # BACKLOG
        # ---------------------------------------------------------

        if action == "BACKLOG":

            start_time = parse_datetime(
                request.form.get("start_time")
            )

            finish_time = parse_datetime(
                request.form.get("finish_time")
            )

            if not start_time or not finish_time:

                return redirect(
                    url_for(
                        "dailylog.new_activity",
                        activity=activity_table,
                        message="Both start and finish date/time are required.Error."
                    )
                )

            start_location = (
                request.form.get("start_location", "")
                .strip()
                or None
            )

            finish_location = (
                request.form.get("finish_location", "")
                .strip()
                or None
            )

            start_latitude = (
                request.form.get("start_latitude")
                or None
            )

            start_longitude = (
                request.form.get("start_longitude")
                or None
            )

            finish_latitude = (
                request.form.get("finish_latitude")
                or None
            )

            finish_longitude = (
                request.form.get("finish_longitude")
                or None
            )

            start_location_source = (
                request.form.get(
                    "start_location_source"
                )
                or None
            )

            finish_location_source = (
                request.form.get(
                    "finish_location_source"
                )
                or None
            )

            if start_latitude:
                start_latitude = float(start_latitude)

            if start_longitude:
                start_longitude = float(start_longitude)

            if finish_latitude:
                finish_latitude = float(finish_latitude)

            if finish_longitude:
                finish_longitude = float(finish_longitude)

            all_columns = get_table_columns(
                conn,
                activity_table
            )

            system_columns = {
                "id",
                "history_id",
                "created_at",
            }

            activity_columns = [
                column
                for column in all_columns
                if column not in system_columns
            ]

            values = []

            for column in activity_columns:

                value = request.form.get(
                    f"field_{column}"
                )

                if value == "":
                    value = None

                values.append(value)

            created_at = get_created_at()
            try:

                conn.execute("BEGIN")

                cursor = conn.execute(
                    """
                    INSERT INTO activity_history (
                        activity_table,
                        start_time,
                        start_location,
                        start_latitude,
                        start_longitude,
                        start_location_source,
                        finish_time,
                        finish_location,
                        finish_latitude,
                        finish_longitude,
                        finish_location_source,
                        status,
                        created_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        'BACKLOG',
                        ?
                    )
                    """,
                    (
                        activity_table,
                        start_time,
                        start_location,
                        start_latitude,
                        start_longitude,
                        start_location_source,
                        finish_time,
                        finish_location,
                        finish_latitude,
                        finish_longitude,
                        finish_location_source,
                        created_at,
                    )
                )

                history_id = cursor.lastrowid

                quoted_table = quote_identifier(
                    activity_table
                )

                quoted_columns = [
                    quote_identifier(column)
                    for column in activity_columns
                ]

                insert_columns = [
                    quote_identifier("history_id")
                ] + quoted_columns

                placeholders = ", ".join(
                    ["?"] * len(insert_columns)
                )

                sql = f"""
                    INSERT INTO {quoted_table}
                    ({", ".join(insert_columns)})
                    VALUES ({placeholders})
                """

                conn.execute(
                    sql,
                    [history_id] + values
                )

                conn.commit()

            except Exception:

                conn.rollback()

                raise


            return redirect(
                url_for("dailylog.new_activity",
                                  message=f"{activity_display_name(activity_table)} added to backlog."
                        )
            )

    finally:

        conn.close()
