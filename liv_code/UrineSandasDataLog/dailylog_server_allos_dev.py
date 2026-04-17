import os
import sqlite3
from flask import Flask, render_template, request, jsonify,redirect
from datetime import datetime, timedelta
from google import genai
from google.genai import types
import threading
from typing import Optional
import platform
import ctypes
from ctypes import wintypes
import markdown
from pathlib import Path
import threading
import subprocess


import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import trafilatura


import pyautogui
import time

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

ai_api_dir = PROJECT_ROOT_SSL / "AI-key"

key_file_path = ai_api_dir / "AI-keys.key"
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


def get_latest_file_url(directory: str) -> str:
    """
    Returns the latest created/modified file in the directory as a file:// URL
    """
    path = Path(directory)

    if not path.exists() or not path.is_dir():
        raise ValueError(f"Invalid directory: {directory}")

    # Get all files (ignore directories)
    files = [f for f in path.iterdir() if f.is_file()]

    if not files:
        raise ValueError("No files found in directory")

    # Pick the most recently modified file
    latest_file = max(files, key=lambda f: f.stat().st_mtime)

    # Convert to file:// URL
    return latest_file.resolve().as_uri()

directory = "/home/dkvlko/Downloads/Telegram Desktop"
#FILE_PATH_GPT = get_latest_file_url(directory)


def load_ai_keys(file_path: Path) -> dict:
    """
    Reads AI API keys from a .key file.
    Expected format per line:
        AI_NAME:API_KEY
    Example:
        Gemini:54656
        OpenAI:sk-xxxxx
    Returns:
        dict -> {AI_NAME: API_KEY}
    """
    ai_keys = {}

    if not file_path.exists():
        raise FileNotFoundError(f"Key file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines or comments
            if not line or line.startswith("#"):
                continue

            if ":" not in line:
                raise ValueError(f"Invalid key format: {line}")

            ai_name, api_key = line.split(":", 1)
            ai_keys[ai_name.strip()] = api_key.strip()

    return ai_keys



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
                try:
                    keys = load_ai_keys(key_file_path)
                    gemini_api_key = keys.get("Gemini")

                    if not gemini_api_key:
                        raise KeyError("Gemini API key not found in key file.")

                    print("Gemini API Key loaded successfully.")
                    # print(gemini_api_key)

                    _gemini_client = genai.Client(api_key=gemini_api_key)

                except Exception as e:
                    print(f"Error loading API keys: {e}")
                    raise   # Fail fast — don’t create invalid client

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


def gemini_generate_search(
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
    # Define the grounding tool
    google_search_tool = types.Tool(
        google_search = types.GoogleSearch()
    )

    for attempt in range(max_retries + 1):
        try:
            # Make the call with the tool enabled
            response = client.models.generate_content(
                model=model, # Use a model that supports grounding
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[google_search_tool]
                )
            )
            # response = client.models.generate_content(
            #    model=model,
            #    contents=prompt
            #)

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

#def rawhtml_generate_search(query):



async def bing_search_raw(query: str) -> str:
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        await page.goto("https://www.bing.com", wait_until="networkidle")
        
        # Handle cookie banner if present
        try:
            accept_btn = page.locator('button:has-text("Accept")')
            if await accept_btn.count() > 0:
                await accept_btn.click()
                await page.wait_for_timeout(1000)
        except:
            pass
        
        # Wait for the textarea search box
        await page.wait_for_selector('textarea[name="q"]', state="visible", timeout=15000)
        
        # Fill and search
        await page.fill('textarea[name="q"]', query)
        await page.keyboard.press("Enter")
        
        # Wait for results to appear
        await page.wait_for_selector('ol#b_results', timeout=15000)
        
        raw_html = await page.content()
        await browser.close()
        return raw_html

def extract_readable_text(html: str) -> str:
    """Extract main content using Trafilatura"""
    # Extract text; include formatting (links, paragraphs)
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        include_links=True,
        include_formatting=True,
        output_format='txt'  # plain text; can also use 'markdown' or 'xml'
    )
    if text is None:
        return "No readable content extracted."
    return text


async def extract_text_gpt(file_path_ubuntu):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(file_path_ubuntu)
        # Load local HTML file
        await page.goto(file_path_ubuntu)

        # Wait for JS to render (adjust if needed)
        await page.wait_for_timeout(3000)

        # Get full rendered HTML
        html = await page.content()

        await browser.close()

        # Extract main text using trafilatura
        extracted = trafilatura.extract(html)

        return extracted


def callAutoSave(prompt):

    # Safety pause: move mouse to corner to abort
    pyautogui.FAILSAFE = True

    # Small delay before starting (gives you time to switch window)
    time.sleep(3)

    # Step 1: Move to (106, 227) and click
    pyautogui.moveTo(106, 227, duration=0.3)
    pyautogui.click()
    time.sleep(5)

    # Step 2: Move to (812, 437) and click
    pyautogui.moveTo(812, 437, duration=0.3)
    pyautogui.click()
    time.sleep(1)

    # Step 3: Type text
    pyautogui.write(prompt, interval=0.05)

    # Step 4: Move to (1169, 437) and click
    pyautogui.moveTo(1169, 437, duration=0.3)
    pyautogui.click()
    time.sleep(20)

    # Step 5: Press Ctrl + S
    pyautogui.hotkey('ctrl', 's')

    #Step 6: Click Save As and wait 3 seconds
    pyautogui.moveTo(1043, 240, duration=0.3)
    pyautogui.click()
    time.sleep(5)
    return

def getGPTAnswer(prompt):
    callAutoSave(prompt)
    print("Auto Save Successful") 
    FILE_PATH_GPT = get_latest_file_url(directory)
    text = asyncio.run(extract_text_gpt(FILE_PATH_GPT))
    
    return text



@app.route("/")
def url_directory():
    routes = []
    # Routes you want to hide
    EXCLUDED_PATHS = {
        "/",
        "/view_results",
        "/insert_entry",
        "/activity",
        "/memo",
        "/screen-off"
    }    

    for rule in app.url_map.iter_rules():
        # Skip static files
        if rule.endpoint == 'static':
            continue

        # Skip excluded URLs
        if str(rule) in EXCLUDED_PATHS:
            continue

        routes.append({
            "name": "Activity",
            "url": str(rule)
        })

    # Sort for clean display
    routes = sorted(routes, key=lambda x: x["url"])

    return render_template("url_directory.html", routes=routes)




@app.route("/copyText", methods=["GET", "POST"])
def copy_text():
    if request.method == "GET":
        # Show the HTML page
        return render_template("copytext.html")

    # POST → run script
    SCRIPT_PATH = os.path.abspath(os.path.join(TEMPLATE_FOLDER, "copytext.sh"))
    #print(SCRIPT_PATH)
    text = request.form.get("text", "")

    subprocess.Popen(
        [SCRIPT_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True
    ).communicate(text)

    # Redirect back to home
    return redirect("/")

@app.route("/log")

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
        submit_type = request.form.get("submit_type")

        print("Received text from /gemini-call:", text)
        
        try:
            #prompt = (
            #    "Answer briefly but keep key details:\n"
            #    + text
            #)
            prompt=text
            if submit_type == "normal":
                answer_text = gemini_generate(prompt)
            elif submit_type == "web":
                answer_text = gemini_generate_search(prompt)


        except Exception as e:    
            print(f"\nError encountered: {e}")
            answer_text = (
            "The AI service is temporarily unavailable or busy. "
            "Please try again in a minute."
            )
        #return render_template("ganswer.html", answer=response.text)
        
        html_answer = render_markdown(answer_text)

        return render_template("geminianswer.html", answer=html_answer)
    # GET: serve the HTML page
    return render_template("gemini_help.html")


@app.route("/rawhtml", methods=["GET", "POST"])
def raw_html():
    if request.method == "GET":
        # Show the HTML page
        return render_template("raw_request.html")

    # POST → to be implemented

    text = "" 

    if request.method == "POST":
        text = (request.form.get("query_text") or "").strip()
        submit_type = request.form.get("submit_type")

        print("Received text from /rawhtml:", text)
        
        try:
            #prompt = (
            #    "Answer briefly but keep key details:\n"
            #    + text
            #)
            prompt=text
            if submit_type == "url":
                #answer_text = "URL Request"
                raw_html = asyncio.run(bing_search_raw(prompt))
            elif submit_type == "bing":
                #answer_text = rawhtml_generate_search(prompt)
                raw_html = asyncio.run(bing_search_raw(prompt))
        
        #readable_text = extract_readable_text(raw_html)
        except Exception as e:    
            print(f"\nError encountered: {e}")
            answer_text = (
            "The Raw HTML service is temporarily unavailable or busy. "
            "Please try again in a minute."
            )
        #return render_template("ganswer.html", answer=response.text)
        readable_text = extract_readable_text(raw_html)

        html_raw = render_markdown(readable_text)

        return render_template("rawhtmlresult.html", answer=html_raw)


@app.route("/gpt2txt",methods=["GET","POST"])
def gptextract():
    if request.method == "GET":
       return render_template("gpt_query.html")
    text=""

    if request.method == "POST":

        text = (request.form.get("query_text") or "").strip()
        submit_type = request.form.get("submit_type")

        print("Received text from /chatgpt_query:", text)
        try :
            #print("hello")
            answer_text = getGPTAnswer(text)

        except Exception as e:    
            print(f"\nError encountered: {e}")
            answer_text = (
            "The AI service is temporarily unavailable or busy. "
            "Please try again in a minute."
            )

        html_answer = render_markdown(answer_text)

        return render_template("chatgptanswer.html", answer=html_answer)
    
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
