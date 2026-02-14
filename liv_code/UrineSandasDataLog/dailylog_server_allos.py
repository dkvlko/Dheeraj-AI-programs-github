import os
import sqlite3
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
from google import genai
import threading
from typing import Optional
import platform
import ctypes
from ctypes import wintypes
import markdown
from pathlib import Path
import threading


#Setting OS neutral variables
CURRENT_FILE = Path(__file__).resolve()

# Project folder (UrineSandasDataLog)
PROJECT_ROOT = CURRENT_FILE.parent

# Project SSL folder (liv_code)
PROJECT_ROOT_SSL = PROJECT_ROOT.parent

# Path to your SQLite database (activities.db)
#BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = PROJECT_ROOT / "activities.db"

#DB_PATH = os.path.join(BASE_DIR, "activities.db")

# Path to your web folder with HTML
#TEMPLATE_FOLDER = r"C:\Users\dheer\OneDrive\DheerajOnHP\liv_code\UrineSandasDataLog\web"
# Build certificate directory path
#one_drive = Path(os.environ["OneDrive"])
cert_dir = PROJECT_ROOT_SSL / "sslcert"
# Files
server_cert = cert_dir / "ubuntu_server.crt"
server_key  = cert_dir / "ubuntu_server.key"

TEMPLATE_FOLDER =  PROJECT_ROOT / "web"
app = Flask(__name__, template_folder=TEMPLATE_FOLDER)

LRESULT = ctypes.c_ssize_t 

# =========================
# Gemini Client Helper
# =========================


_gemini_client_lock = threading.Lock()
_gemini_client: Optional[genai.Client] = None


def get_gemini_client() -> genai.Client:
    """
    Singleton Gemini client.
    Creates once, reuses everywhere.
    Thread-safe for Flask.
    """
    global _gemini_client

    if _gemini_client is None:
        with _gemini_client_lock:
            if _gemini_client is None:
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise RuntimeError(
                        "GEMINI_API_KEY environment variable not set."
                    )

                _gemini_client = genai.Client(api_key=api_key)

    return _gemini_client


def gemini_generate(
    prompt: str,
    model: str = "gemini-2.5-flash",
    max_retries: int = 2
) -> str:
    """
    Central Gemini invocation wrapper.
    Handles retries + errors.
    """

    client = get_gemini_client()

    last_error = None

    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )

            if not response or not response.text:
                raise RuntimeError("Empty Gemini response")

            return response.text.strip()

        except Exception as e:
            last_error = e
            print(f"[Gemini retry {attempt+1}] Error:", e)

    raise RuntimeError(f"Gemini failed after retries: {last_error}")


def render_markdown(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["extra", "codehilite", "tables"]
    )


def turn_off_screen(timeout_ms: int = 2000) -> None:
    if platform.system() != "Windows":
        raise OSError("This function only works on Windows.")

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    HWND_BROADCAST = wintypes.HWND(0xFFFF)
    WM_SYSCOMMAND = wintypes.UINT(0x0112)
    SC_MONITORPOWER = wintypes.WPARAM(0xF170)
    lparam = wintypes.LPARAM(2)  # 2 = power off

    SendMessageTimeout = user32.SendMessageTimeoutW
    SendMessageTimeout.restype = LRESULT
    SendMessageTimeout.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.DWORD)
    ]

    SMTO_ABORTIFHUNG = 0x0002
    result = wintypes.DWORD(0)

    ret = SendMessageTimeout(
        HWND_BROADCAST,
        WM_SYSCOMMAND,
        SC_MONITORPOWER,
        lparam,
        SMTO_ABORTIFHUNG,
        wintypes.UINT(timeout_ms),
        ctypes.byref(result)
    )

    if ret == 0:
        err = ctypes.get_last_error()
        raise OSError(f"SendMessageTimeout failed (GetLastError={err})")



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

@app.route("/game-help", methods=["GET", "POST"])
def game_help():
    text = "" 
    text_choice = ""
    if request.method == "POST":
        text = (request.form.get("query_text") or "").strip()
        text_choice = (request.form.get("game_choice") or "").strip()

        print("Received text from /game-help:", text)
        print("Selected game:", text_choice)
        
        try:
            prompt = (
                f"How can I achieve the following goal in the standard windows 10 game "
                f"'{text_choice}'? "
                f"Please answer in as few words as possible. "
                f"I am using a Microsoft controller, keyboard and mouse. "
                f"Give answer for each case if possible. "
                f"Question: {text}"
            )

            answer_text = gemini_generate(prompt)

        except Exception as e:    
            print(f"\nError encountered: {e}")
            return "Gemini API error", 500
        
        final_answer = f"{text_choice} : {answer_text}"
        
        html_answer = render_markdown(final_answer)

        return render_template("ganswer.html", answer=html_answer)

    # GET: serve the HTML page
    return render_template("game_help.html")


@app.route("/hindi2marathi-transcribe", methods=["GET", "POST"])
def hindi2marathi_transcribe():
    if request.method == "GET":
        return render_template("transcribe.html")

    # POST handling:
    text = (request.form.get("text") or "").strip()
    print("Received text from /hindi-transcribe:", text)

    try:
        prompt = (
            "Translate Hindi to Marathi. "
            "Fix grammar if needed. "
            "Keep answer concise:\n"
            + text
        )

        answer_text = gemini_generate(prompt)

    except Exception as e:
        print(f"\nError encountered: {e}")
        return "Gemini API error", 500

    return render_template("ganswerhindi2marathi.html", answer=answer_text)


@app.route("/screen-off", methods=["POST", "GET"])
def screen_off_handler():
    """
    Endpoint to turn off the screen.
    Using POST is recommended for safety, but GET also works here.
    """
    try:
        turn_off_screen()
        return jsonify({"status": "ok", "message": "screen-off command sent"}), 200
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500

@app.route("/gemini-call", methods=["GET", "POST"])
def gemini_help():
    text = "" 

    if request.method == "POST":
        text = (request.form.get("query_text") or "").strip()

        print("Received text from /gemini-call:", text)
        
        try:
            prompt = (
                "Answer briefly but keep key details:\n"
                + text
            )

            answer_text = gemini_generate(prompt)

        except Exception as e:    
            print(f"\nError encountered: {e}")
        
        #return render_template("ganswer.html", answer=response.text)
        
        html_answer = render_markdown(answer_text)

        return render_template("geminianswer.html", answer=html_answer)
    # GET: serve the HTML page
    return render_template("gemini_help.html")


if __name__ == "__main__":
    # You can change port if you want, e.g. port=8000
    #app.run(host="0.0.0.0", port=8000, debug=True)
    app.run(
        host="0.0.0.0",          # important so LAN devices can connect
        port=8000,
       debug=True,
         #ssl_context=("C:/ssl/cert.pem", "C:/ssl/key.pem")  # use forward slashes or raw string
         ssl_context=(str(server_cert), str(server_key))
    )
