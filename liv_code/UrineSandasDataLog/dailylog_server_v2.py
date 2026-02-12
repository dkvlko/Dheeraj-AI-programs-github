import os
import sqlite3
from flask import Flask, render_template, request
from datetime import datetime, timedelta

# Path to your SQLite database (activities.db)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "activities.db")

# Path to your web folder with HTML
TEMPLATE_FOLDER = r"C:\Users\dheer\OneDrive\DheerajOnHP\liv_code\UrineSandasDataLog\web"

app = Flask(__name__, template_folder=TEMPLATE_FOLDER)

def get_table_names():
    """
    Return list of table names in activities.db
    (excluding internal sqlite_ tables).
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]

def is_valid_table(name: str) -> bool:
    return name in get_table_names()


def getViewTable(activity):
    # Renders a mobile-friendly form that asks for period (listb)
    return render_template("view_form.html", activity=activity)


def getInsertTable(activity):
    if activity=="Memo":
        return render_template("memo.html")
    else:
        # Renders a mobile-friendly form that asks for DateTime (listc)
        now = datetime.now()
        now_display = now.strftime("%Y-%m-%d %H:%M:%S")
        return render_template("insert_form.html", activity=activity, now_display=now_display)


@app.route("/")

def index():
    tables = get_table_names()  # e.g. ["Sandas", "Urine"]
    return render_template("activity.html", tables=tables)


@app.route("/activity")
def activity_action():
    event_value = request.args.get("event", "")
    execute_value = request.args.get("execute", "")

    if execute_value == "View":
        return getViewTable(event_value)
    elif execute_value == "Insert":
        return getInsertTable(event_value)
    else:
        return "<html><body><p>Unknown action</p></body></html>"

@app.route("/view_results", methods=["POST"])
def view_results():
    activity = request.form.get("activity", "")
    period = request.form.get("listb", "")

    if not is_valid_table(activity):
        return "<html><body><p>Unknown table.</p></body></html>"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Base query
    if activity == "Memo":
        query = f"SELECT SNo, Note, DateTime FROM {activity}"
    else:
        query = f"SELECT SerialNumber, Activity, DateTime FROM {activity}"
    params = []
    order_clause = " ORDER BY DateTime DESC"

    if period == "last 20 enteries":
        query += order_clause + " LIMIT 20"
    elif period == "last one week":
        cutoff = datetime.now() - timedelta(days=7)
        query += " WHERE DateTime >= ? " + order_clause
        params.append(cutoff.strftime("%Y-%m-%d %H:%M:%S"))
    elif period == "last one month":
        cutoff = datetime.now() - timedelta(days=30)
        query += " WHERE DateTime >= ? " + order_clause
        params.append(cutoff.strftime("%Y-%m-%d %H:%M:%S"))
    elif period == "All enteries":
        query += order_clause
    else:
        conn.close()
        return "<html><body><p>Unknown period.</p></body></html>"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    entries = [
        {"serial": r[0], "activity": r[1], "datetime": r[2]}
        for r in rows
    ]

    return render_template(
        "view_results.html",
        activity=activity,
        period=period,
        entries=entries,
    )

@app.route("/insert_entry", methods=["POST"])
def insert_entry():
    activity = request.form.get("activity", "")
    dt_choice = request.form.get("listc", "")

    if not is_valid_table(activity):
        return "<html><body><p>Unknown table.</p></body></html>"

    if dt_choice == "Now":
        dt_value = datetime.now()
    else:
        return "<html><body><p>Unknown date selection.</p></body></html>"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {activity} (Activity, DateTime) VALUES (?, ?)",
        (activity, dt_value.strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()

    # Just show "Success" via template
    return render_template("success.html")

@app.route("/memo", methods=["GET", "POST"])
def memo():
    if request.method == "POST":
        note = request.form.get("memo", "").strip()

        if note:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("INSERT INTO Memo (Note) VALUES (?)", (note,))
            conn.commit()
            conn.close()

        # Always show success page after POST (even if empty)
        return render_template("success.html")

    # GET: just show the memo form
    return render_template("memo.html")

if __name__ == "__main__":
    # You can change port if you want, e.g. port=8000
    app.run(host="0.0.0.0", port=8000, debug=True)
