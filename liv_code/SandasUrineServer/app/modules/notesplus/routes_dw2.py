from flask import render_template, request, jsonify
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


from flask_socketio import emit
from . import notes_bp
from . import static
from app import socketio



# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

# Change this if your activities.db is somewhere else.
DATABASE = Path("/data/BLOBS/SandasServ_BLOB/activities.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    # Make sure SQLite enforces foreign keys.
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# ---------------------------------------------------------
# Time
# ---------------------------------------------------------

def utc_now():
    """
    Return current UTC time as ISO-8601 text.
    Example:
        2026-09-19T04:15:23.123456+00:00
    """
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------
# Find or create topic
# ---------------------------------------------------------

def get_or_create_topic(conn, topic_name):
    """
    Return the topic ID.

    If the topic doesn't exist, create it.
    """

    topic_name = topic_name.strip()

    if not topic_name:
        raise ValueError("Topic cannot be empty at this stage.")

    row = conn.execute(
        """
        SELECT id
        FROM Topics
        WHERE name = ?
        """,
        (topic_name,)
    ).fetchone()

    if row:
        return row["id"]

    created_at = utc_now()

    cursor = conn.execute(
        """
        INSERT INTO Topics (name, created_at)
        VALUES (?, ?)
        """,
        (topic_name, created_at)
    )

    return cursor.lastrowid


# ---------------------------------------------------------
# Main page
# ---------------------------------------------------------

@notes_bp.route("/", methods=["GET"])
def notesplus():
    """
    Display the first note.
    """

    conn = get_db()

    note = conn.execute(
        """
        SELECT
            Notes.id,
            Notes.title,
            Notes.content,
            Notes.created_at,
            Notes.modified_at,
            Topics.name AS topic
        FROM Notes
        JOIN Topics
            ON Notes.topic_id = Topics.id
        WHERE Notes.is_deleted = 0
        ORDER BY Notes.id DESC
        LIMIT 1
        """
    ).fetchone()

    conn.close()

# sqlite3.Row → normal Python dictionary
    if note is not None:
        note = dict(note)

    return render_template(
        "notesplus.html",
        note=note
    )

# ---------------------------------------------------------
# Create the initial test note
# ---------------------------------------------------------

@notes_bp.route("/create-test", methods=["POST"])
def create_test():

    conn = get_db()

    try:

        title = "Test"
        topic = "Test"

        # Markdown source.
        #
        # Markdown itself doesn't have underline syntax.
        # HTML <u> is therefore embedded inside Markdown.
        content = "**<u>Hello World</u>**"

        now = utc_now()

        topic_id = get_or_create_topic(
            conn,
            topic
        )

        cursor = conn.execute(
            """
            INSERT INTO Notes
            (
                title,
                topic_id,
                content,
                created_at,
                modified_at,
                is_deleted
            )
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                title,
                topic_id,
                content,
                now,
                now
            )
        )

        note_id = cursor.lastrowid

        conn.commit()

        return jsonify({
            "success": True,
            "note_id": note_id,
            "message": "Test note created."
        })

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500

    finally:
        conn.close()


# ---------------------------------------------------------
# Get note
# ---------------------------------------------------------

@notes_bp.route("/note/<int:note_id>", methods=["GET"])
def get_note(note_id):

    conn = get_db()

    note = conn.execute(
        """
        SELECT
            Notes.id,
            Notes.title,
            Notes.content,
            Notes.created_at,
            Notes.modified_at,
            Topics.name AS topic
        FROM Notes
        JOIN Topics
            ON Notes.topic_id = Topics.id
        WHERE Notes.id = ?
          AND Notes.is_deleted = 0
        """,
        (note_id,)
    ).fetchone()

    conn.close()

    if note is None:
        return jsonify({
            "success": False,
            "error": "Note not found."
        }), 404

    return jsonify({
        "success": True,
        "note": dict(note)
    })


# ---------------------------------------------------------
# Save edited note
# ---------------------------------------------------------

@notes_bp.route("/save", methods=["POST"])
def save_note():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "error": "No JSON data received."
        }), 400

    note_id = data.get("id")
    title = (data.get("title") or "").strip()
    topic = (data.get("topic") or "").strip()
    content = data.get("content") or ""

    if not title:
        return jsonify({
            "success": False,
            "error": "Title is required."
        }), 400

    # Requirement:
    # if topic is blank, title becomes topic.
    if not topic:
        topic = title

    conn = get_db()

    try:

        topic_id = get_or_create_topic(
            conn,
            topic
        )

        now = utc_now()

        if note_id:

            cursor = conn.execute(
                """
                UPDATE Notes
                SET
                    title = ?,
                    topic_id = ?,
                    content = ?,
                    modified_at = ?
                WHERE id = ?
                  AND is_deleted = 0
                """,
                (
                    title,
                    topic_id,
                    content,
                    now,
                    note_id
                )
            )

            if cursor.rowcount == 0:
                conn.rollback()

                return jsonify({
                    "success": False,
                    "error": "Note not found."
                }), 404

        else:

            cursor = conn.execute(
                """
                INSERT INTO Notes
                (
                    title,
                    topic_id,
                    content,
                    created_at,
                    modified_at,
                    is_deleted
                )
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (
                    title,
                    topic_id,
                    content,
                    now,
                    now
                )
            )

            note_id = cursor.lastrowid

        conn.commit()

        return jsonify({
            "success": True,
            "note_id": note_id,
            "modified_at": now
        })

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500

    finally:
        conn.close()
