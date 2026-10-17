from flask import render_template, request, jsonify
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask_socketio import emit

from . import notes_bp
from app import socketio


# =========================================================
# Database
# =========================================================

DATABASE = Path(
    "/data/BLOBS/SandasServ_BLOB/activities.db"
)


def get_db():
    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON")

    return conn


# =========================================================
# Time
# =========================================================

def utc_now():
    return datetime.now(timezone.utc).isoformat()


# =========================================================
# Topic
# =========================================================

def get_or_create_topic(conn, topic_name):

    topic_name = topic_name.strip()

    if not topic_name:
        raise ValueError("Topic cannot be empty.")

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

    cursor = conn.execute(
        """
        INSERT INTO Topics
        (
            name,
            created_at
        )
        VALUES (?, ?)
        """,
        (
            topic_name,
            utc_now()
        )
    )

    return cursor.lastrowid


# =========================================================
# LIST NOTES
# =========================================================

@notes_bp.route("/", methods=["GET"])
def notesplus():

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            Notes.id,
            Notes.title,
            Notes.created_at,
            Notes.modified_at,
            Notes.is_pinned,
            Topics.name AS topic
        FROM Notes
        JOIN Topics
            ON Notes.topic_id = Topics.id
        WHERE Notes.is_deleted = 0
        ORDER BY
            Notes.is_pinned DESC,
            Notes.modified_at DESC
        """
    ).fetchall()

    conn.close()

    notes = [dict(row) for row in rows]

    return render_template(
        "notesplus.html",
        notes=notes
    )


# =========================================================
# NEW NOTE
# =========================================================

@notes_bp.route("/new", methods=["GET"])
def new_note():

    return render_template(
        "notesplus.html",
        note={
            "id": None,
            "title": "",
            "topic": "",
            "content": "",
            "created_at": "",
            "modified_at": "",
            "is_pinned": 0
        },
        new_note=True
    )

# =========================================================
# VIEW / EDIT NOTE
# =========================================================

@notes_bp.route("/note/<int:note_id>", methods=["GET"])
def view_note(note_id):

    conn = get_db()

    row = conn.execute(
        """
        SELECT
            Notes.id,
            Notes.title,
            Notes.content,
            Notes.created_at,
            Notes.modified_at,
            Notes.is_pinned,
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

    if row is None:

        return (
            "Note not found",
            404
        )

    note = dict(row)

    return render_template(
        "notesplus.html",
        note=note
    )


# =========================================================
# CREATE TEST NOTE
# =========================================================

@notes_bp.route("/create-test", methods=["POST"])
def create_test():

    conn = get_db()

    try:

        title = "Test"
        topic = "Test"

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
                is_deleted,
                is_pinned
            )
            VALUES (?, ?, ?, ?, ?, 0, 0)
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
            "note_id": note_id
        })

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500

    finally:

        conn.close()


# =========================================================
# GET NOTE
# =========================================================

@notes_bp.route("/note-data/<int:note_id>", methods=["GET"])
def get_note(note_id):

    conn = get_db()

    row = conn.execute(
        """
        SELECT
            Notes.id,
            Notes.title,
            Notes.content,
            Notes.created_at,
            Notes.modified_at,
            Notes.is_pinned,
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

    if row is None:

        return jsonify({
            "success": False,
            "error": "Note not found."
        }), 404

    return jsonify({
        "success": True,
        "note": dict(row)
    })


# =========================================================
# SAVE NOTE - HTTP fallback / explicit Save
# =========================================================

@notes_bp.route("/save", methods=["POST"])
def save_note():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "error": "No JSON data received."
        }), 400

    note_id = data.get("id")

    title = (
        data.get("title") or ""
    ).strip()

    topic = (
        data.get("topic") or ""
    ).strip()

    content = data.get("content") or ""

    if not title:

        return jsonify({
            "success": False,
            "error": "Title is required."
        }), 400

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
                    is_deleted,
                    is_pinned
                )
                VALUES (?, ?, ?, ?, ?, 0, 0)
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


# =========================================================
# PIN / UNPIN
# =========================================================

@notes_bp.route("/toggle-pin/<int:note_id>", methods=["POST"])
def toggle_pin(note_id):

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT is_pinned
            FROM Notes
            WHERE id = ?
              AND is_deleted = 0
            """,
            (note_id,)
        ).fetchone()

        if row is None:

            return jsonify({
                "success": False,
                "error": "Note not found."
            }), 404

        new_value = (
            0
            if row["is_pinned"]
            else 1
        )

        conn.execute(
            """
            UPDATE Notes
            SET is_pinned = ?
            WHERE id = ?
            """,
            (
                new_value,
                note_id
            )
        )

        conn.commit()

        return jsonify({
            "success": True,
            "is_pinned": bool(new_value)
        })

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500

    finally:

        conn.close()


# =========================================================
# DELETE ONE OR MORE NOTES
# =========================================================

@notes_bp.route("/delete", methods=["POST"])
def delete_notes():

    data = request.get_json(silent=True)

    if not data:

        return jsonify({
            "success": False,
            "error": "No JSON data received."
        }), 400

    note_ids = data.get("ids", [])

    if not isinstance(note_ids, list):

        return jsonify({
            "success": False,
            "error": "ids must be a list."
        }), 400

    if not note_ids:

        return jsonify({
            "success": False,
            "error": "No notes selected."
        }), 400

    conn = get_db()

    try:

        placeholders = ",".join(
            "?" for _ in note_ids
        )

        conn.execute(
            f"""
            UPDATE Notes
            SET is_deleted = 1
            WHERE id IN ({placeholders})
            """,
            tuple(note_ids)
        )

        conn.commit()

        return jsonify({
            "success": True,
            "deleted": len(note_ids)
        })

    except Exception as exc:

        conn.rollback()

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500

    finally:

        conn.close()


# =========================================================
# WEBSOCKET AUTO SAVE
# =========================================================

@socketio.on("notesplus_autosave")
def notesplus_autosave(data):

    if not data:

        emit(
            "notesplus_autosave_result",
            {
                "success": False,
                "error": "No data received."
            }
        )

        return

    note_id = data.get("id")

    title = (
        data.get("title") or ""
    ).strip()

    topic = (
        data.get("topic") or ""
    ).strip()

    content = data.get("content") or ""

    if not title:

        emit(
            "notesplus_autosave_result",
            {
                "success": False,
                "error": "Title is required."
            }
        )

        return

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

                emit(
                    "notesplus_autosave_result",
                    {
                        "success": False,
                        "error": "Note not found."
                    }
                )

                return

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
                    is_deleted,
                    is_pinned
                )
                VALUES (?, ?, ?, ?, ?, 0, 0)
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

        emit(
            "notesplus_autosave_result",
            {
                "success": True,
                "note_id": note_id,
                "modified_at": now
            }
        )

    except Exception as exc:

        conn.rollback()

        emit(
            "notesplus_autosave_result",
            {
                "success": False,
                "error": str(exc)
            }
        )

    finally:

        conn.close()
