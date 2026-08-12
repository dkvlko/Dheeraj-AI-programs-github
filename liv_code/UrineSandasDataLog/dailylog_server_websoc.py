import os
import random
import sqlite3
from flask import Flask, render_template, request, jsonify,redirect,send_file,abort,template_rendered,Response
from datetime import datetime, timedelta,timezone
from google import genai
import json
from google.genai import types
import threading
from typing import Optional
import platform
import ctypes
from ctypes import wintypes
import markdown
from pathlib import Path
import subprocess
import mimetypes
from flask import after_this_request
import tempfile
import zipfile
import requests

from blinker import signal
import re
import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import trafilatura


import pyautogui
import time
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

from flask_socketio import SocketIO,emit
import uuid

import shutil

mouse_lock = threading.Lock()

pyautogui.FAILSAFE = False

#Setting OS neutral variables
CURRENT_FILE = Path(__file__).resolve()

# Project folder (UrineSandasDataLog)
PROJECT_ROOT = CURRENT_FILE.parent

# Project SSL folder (liv_code)
PROJECT_ROOT_SSL = PROJECT_ROOT.parent

# Path to your SQLite database (activities.db)
#BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = PROJECT_ROOT / "activities.db"

BASE_PATH = Path("/").resolve()
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
STATIC_FOLDER = TEMPLATE_FOLDER / "static"

#For Music player

DOWNLOAD_DIR = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/SpotifyMusicRIP")
AD_FILE = "Shaitaan.mp3"


ANNOUNCEMENT_DIR = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Announcements"
)
BLOBS_DIR =  Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/Temp"
)

PLAYLIST_LOG = BLOBS_DIR / "FlagshipPlaylist.log"

LAN_CLOUD_FOLDER = Path(
    "/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/SharedDataOnLan"
)

UPLOAD_TEMP_FOLDER = LAN_CLOUD_FOLDER / ".upload_temp"

UPLOAD_TEMP_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)
#Open Maps settings
MARTIN_URL = "http://127.0.0.1:3000"

#Cache Directory#
HOLIDAY_CACHE_FILE = PROJECT_ROOT / "BLOBS" / "holiday_cache.json"

HOLIDAY_CACHE_LOCK = threading.Lock()
# ------------------------------------------------------------
# Global data used by websocket handlers
# ------------------------------------------------------------


LANcloud_ID_MAP = {}
LANcloud_JSON = {}
#Global pointers for songs
_current_item = None
_previous_item = None
_next_item = None

# Cached playlist
_playlist = []
_index = 0

#Server declaration#

app = Flask(
        __name__,
        template_folder=TEMPLATE_FOLDER,
        static_folder=STATIC_FOLDER,
        static_url_path="/static"
        )

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode = "threading"
)

#Functions declaration#

# -------------------------
# TEMPLATE TRACE LOGGER
# -------------------------


def template_logger(sender, template, context, **extra):
    print(f"TEMPLATE USED: {template.name}")

template_rendered.connect(template_logger, app)

LRESULT = ctypes.c_ssize_t 

def get_cached_holiday_answer():
    """
    Return today's holiday answer.

    Gemini is called only once per calendar day.
    The result is permanently cached on disk until
    a new date requires a new answer.
    """

    now = datetime.now().astimezone()

    today = now.strftime("%Y-%m-%d")

    # Make sure BLOBS exists
    HOLIDAY_CACHE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with HOLIDAY_CACHE_LOCK:

        # -------------------------------------------------
        # Try existing cache
        # -------------------------------------------------

        if HOLIDAY_CACHE_FILE.exists():

            try:

                with open(
                    HOLIDAY_CACHE_FILE,
                    "r",
                    encoding="utf-8"
                ) as f:

                    cache = json.load(f)

                cached_date = cache.get("date")
                cached_answer = cache.get("answer")

                if (
                    cached_date == today
                    and cached_answer
                ):

                    print(
                        f"Holiday cache HIT: {today}"
                    )

                    return cached_answer

            except Exception as e:

                print(
                    f"Holiday cache read error: {e}"
                )


        # -------------------------------------------------
        # Cache miss — call Gemini
        # -------------------------------------------------

        date_text = now.strftime(
            "%A, %d %B %Y"
        )

        prompt = f"""
Today is {date_text}.

Answer the question:

"Is there a bank or hindu holiday today and why?"

Location:
Lucknow, Uttar Pradesh, India.

Give ONLY a very brief answer in exactly 2-3 lines.

Line 1:
Clearly say either:
"Yes, today is a holiday."
or
"Today is not a holiday."

Line 2-3:
Give the reason and name of the holiday if applicable.
If it is not a holiday, briefly state that no major public
holiday is observed today.

Do not use markdown.
Do not use bullet points.
Do not mention that you are an AI.
Do not add any additional explanation.
"""

        print(
            f"Holiday cache MISS: {today}"
        )

        print(
            "Calling Gemini for today's holiday..."
        )

        answer_text = gemini_generate(
            prompt
        )

        answer_text = answer_text.strip()


        # -------------------------------------------------
        # Save new answer
        # -------------------------------------------------

        cache = {
            "date": today,
            "generated_at": now.isoformat(),
            "answer": answer_text
        }

        try:

            with open(
                HOLIDAY_CACHE_FILE,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    cache,
                    f,
                    ensure_ascii=False,
                    indent=4
                )

            print(
                f"Holiday answer cached for {today}"
            )

        except Exception as e:

            print(
                f"Holiday cache write error: {e}"
            )


        return answer_text

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

    
    match = re.match(r"Sandas",activity)
    if match :
        in_activity=activity.split("Sandas-", 1)[1].strip()
        activity = "Sandas"
    
    if activity=="Memo":
        return render_template("memo.html")
    else:
        # Renders a mobile-friendly form that asks for DateTime (listc)
        now = datetime.now()
        now_display = now.strftime("%Y-%m-%d %H:%M:%S")
        entries = [
            {
                "name": "Dheeraj",
                "age": "48",
                "address": "Lucknow",
                "activity": activity,
                "in_activity": in_activity,
                "datetime": now_display,
                "amount": "S",
                "quality": "V",
                "srating": "S"
            }
        ]

        return render_template("insert_form.html", activity=activity, entries=entries)
        #return render_template("insert_form.html", activity=activity, now_display=now_display)

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

def song_metadata(filename):
    path = DOWNLOAD_DIR / filename

    result = {
        "title": path.stem,
        "album": "",
        "artist": ""
    }

    try:
        tags = EasyID3(path)

        result["title"] = tags.get("title", [path.stem])[0]
        result["album"] = tags.get("album", [""])[0]
        result["artist"] = tags.get("artist", [""])[0]

    except Exception:
        try:
            audio = MP3(path)
            result["title"] = audio.get("TIT2", result["title"]).text[0]
            result["album"] = audio.get("TALB", "").text[0]
            result["artist"] = audio.get("TPE1", "").text[0]
        except Exception:
            pass

    return result

def advance_song():
    """Normal playback: advance to the next playlist item."""

    global _index

    if not _playlist:
        rebuild_playlist()

    _index += 1

    if _index >= len(_playlist):
        rebuild_playlist()
    
    update_song_pointers()

def rebuild_playlist():

    global _playlist, _index

    songs = [
        p.name
        for p in DOWNLOAD_DIR.glob("*.mp3")
        if p.name.lower() != AD_FILE.lower()
    ]

    random.shuffle(songs)

    playlist = []

    while songs:

        count = random.randint(3, 4)

        for _ in range(count):

            if not songs:
                break

            song = songs.pop()

            wav = ANNOUNCEMENT_DIR / (Path(song).stem + ".wav")

            if wav.exists():
                playlist.append({
                    "type": "announcement",
                    "path": wav
                })

            playlist.append({
                "type": "song",
                "path": DOWNLOAD_DIR / song
            })

        ad_wav = ANNOUNCEMENT_DIR / (Path(AD_FILE).stem + ".wav")
        ad_mp3 = DOWNLOAD_DIR / AD_FILE

        if ad_wav.exists():
            playlist.append({
                "type": "announcement",
                "path": ad_wav
            })

        if ad_mp3.exists():
            playlist.append({
                "type": "song",
                "path": ad_mp3
            })

    _playlist = playlist
    _index = 0
    
    update_song_pointers()
    with open(PLAYLIST_LOG, "a", encoding="utf-8") as f:

        f.write("\n")
        f.write("=" * 80 + "\n")
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        f.write("\n")
        f.write("=" * 80 + "\n")

        for n, item in enumerate(_playlist, 1):
            f.write(
                f"{n:03d}  "
                f"{item['type']:13s}  "
                f"{item['path'].name}\n"
            )


def current_song():
    global _index

    if not _playlist:
        rebuild_playlist()

    if _index >= len(_playlist):
        rebuild_playlist()
    return _playlist[_index]["path"]


def update_song_pointers():
    """Update previous/current/next pointers and log them."""

    global _current_item, _previous_item, _next_item

    if not _playlist:
        return

    _current_item = _playlist[_index]

    if _index > 0:
        _previous_item = _playlist[_index - 1]
    else:
        _previous_item = None

    if _index < len(_playlist) - 1:
        _next_item = _playlist[_index + 1]
    else:
        _next_item = None

    #print()
    #print("=" * 70)
    #print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    #print("Previous :", _previous_item["path"].name if _previous_item else "<None>")
    #print("Current  :", _current_item["path"].name)
    #print("Next     :", _next_item["path"].name if _next_item else "<None>")

    #print("=" * 70)

def next_song():
    """Next button: jump to the next announcement."""

    global _index

    if not _playlist:
        rebuild_playlist()

    i = _index + 1

    while i < len(_playlist):

        if _playlist[i]["type"] == "announcement":
            _index = i
            found = True
            break

        i += 1

    # End of playlist
    if not found:
        rebuild_playlist()

    update_song_pointers()

def previous_song():
    """Previous button: jump to the previous song's announcement."""

    global _index

    if not _playlist:
        rebuild_playlist()

    # Start searching before the current item.
    i = _index - 1

    # If currently on a song, skip its own announcement.
    if (
        _playlist[_index]["type"] == "song"
        and i >= 0
        and _playlist[i]["type"] == "announcement"
    ):
        i -= 1

    while i >= 0:
        if _playlist[i]["type"] == "announcement":
            _index = i
            return
        i -= 1

    _index = 0

    update_song_pointers()


# ------------------------------------------------------------
# Build directory listing
# ------------------------------------------------------------

def BuildLANcloudDirectoryJSON(folder=None):

    global LANcloud_ID_MAP
    global LANcloud_JSON

    if folder is None:
        folder = LAN_CLOUD_FOLDER

    LANcloud_ID_MAP.clear()

    entries = []

    
    ############################################################
    # Parent Directory (..)
    ############################################################

    if folder != LAN_CLOUD_FOLDER:

        LANcloud_ID_MAP["__PARENT__"] = folder.parent

        entries.append(
            {
                "id": "__PARENT__",
                "name": "..",
                "type": "directory",
                "size": 0,
                "modified": ""
            }
        )

    ############################################################
    # Current Directory
    ############################################################

    for item in sorted(
            folder.iterdir(),
            key=lambda p: (p.is_file(), p.name.lower())):

        item_id = uuid.uuid4().hex

        LANcloud_ID_MAP[item_id] = item

        stat = item.stat()

        entries.append(
            {
                "id": item_id,
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": stat.st_size,
                "modified":
                    datetime.fromtimestamp(
                        stat.st_mtime
                    ).strftime("%d-%b-%Y %H:%M:%S")
            }
        )

    ############################################################
    # Relative Path
    ############################################################

    if folder == LAN_CLOUD_FOLDER:

        current_directory = ""

    else:

        current_directory = str(
            folder.relative_to(LAN_CLOUD_FOLDER)
        )

    ############################################################
    # JSON returned to JavaScript
    ############################################################

    LANcloud_JSON = {

        "command": "directory_listing",

        "current_directory": current_directory,

        "entries": entries
    }

#Url handlers beging here


@app.route("/my/")
def mypage():
    return redirect("/")

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
        "/screen-off",
        "/flagship/current",
        "/flagship/info",
        "/flagship/next",
        "/flagship/previous",
        "/flagship/advance",
        "/holiday-today",
        "/flagship/status",
        "/LANcloud/list",
        "/file-operation-upload",
        "/file-operation-download",
        "/file-operation",
        "/LANcloud/change-directory",
        "/file-operation-new-directory",
        "/ufiles/<path:req_path>"
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
    new_tables = []

    for t in tables:
        if t == "Sandas":
            new_tables.append("Sandas-Sandas")
            new_tables.append("Sandas-Urine")
        else:
            new_tables.append(t)

    tables = new_tables    
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

    match = re.match(r"Sandas",activity)
    if match :
        in_activity=activity.split("Sandas", 1)[1].strip()
        activity = "Sandas"

    if not is_valid_table(activity):
        return "<html><body><p>Unknown table.</p></body></html>"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
        
    # Base query
    if activity == "Memo":
        query = f"SELECT SNo, Note, DateTime FROM {activity}"
    else:
        query = f"SELECT SNo, Name,Age,Address,Activity, DateTime,Amount,Quality,SRating,Duration FROM {activity}"
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
    if activity == "Memo" :
        entries =[
                {"sno":r[0],"note":r[1],"datetime":r[2]}
                    for r in rows
                ]
    else:
        entries = [
                {"sno": r[0], "name": r[1], "age": r[2], "address": r[3], "activity": r[4], "datetime": r[5], "amount": r[6], "quality": r[7], "srating": r[8], "duration": r[9]}
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
    in_activity = request.form.get("in_activity", "")
    name ="Dheeraj"
    age ="48"
    address="Lucknow"
    amount = request.form.get("amount", "")
    quality = request.form.get("quality", "")
    srating = request.form.get("srating", "")
    duration = request.form.get("duration","")
    if not is_valid_table(activity):
        return "<html><body><p>Unknown table.</p></body></html>"

    if dt_choice == "Now":
        dt_value = datetime.now()
    else:
        return "<html><body><p>Unknown date selection.</p></body></html>"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {activity} (Name,Age,Address,Activity,DateTime,Amount,Quality,SRating,Duration) VALUES (?,?,?,?,?,?,?,?,?)",
        (name,age,address,in_activity, dt_value.strftime("%Y-%m-%d %H:%M:%S"),amount,quality,srating,duration),
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



@app.route("/ufiles", defaults={"req_path": ""})
@app.route("/ufiles/<path:req_path>")
def ufiles(req_path):

    full_path = (BASE_PATH / req_path).resolve()

    # Security check
    if not str(full_path).startswith(str(BASE_PATH)):
        abort(403)

    if not full_path.exists():
        abort(404)

    # File handling
    if full_path.is_file():
        mime_type, _ = mimetypes.guess_type(str(full_path))

        return send_file(
            full_path,
            mimetype=mime_type
        )

    # Directory listing
    items = []

    try:
        for item in sorted(full_path.iterdir()):

            relative = item.relative_to(BASE_PATH)

            items.append({
                "name": item.name,
                "is_dir": item.is_dir(),
                "url": "/ufiles/" + str(relative)
            })

    except PermissionError:
        return "Permission denied", 403

    parent = None

    if full_path != BASE_PATH:
        parent_rel = full_path.parent.relative_to(BASE_PATH)
        parent = "/ufiles/" + str(parent_rel)

    return render_template(
        "file_browser.html",
        items=items,
        current_path="/" + req_path,
        parent=parent
    )
@app.route("/controlTV")
def control_tv():
    return render_template("controlTV.html")


@socketio.on("mouse_move")
def mouse_move(data):
    dx = float(data["dx"])
    dy = float(data["dy"])

    gain = 2.0
    
    with mouse_lock:
        pyautogui.moveRel(
            dx * gain,
            dy * gain,
            duration=0
        )
@socketio.on("mouse_click")
def mouse_click(data):
    with mouse_lock:
        pyautogui.click()


@socketio.on("mouse_double")
def mouse_double(data):
    with mouse_lock:
        pyautogui.doubleClick()

@socketio.on("connect")
def connected():
    print("iPhone connected")

@socketio.on("disconnect")
def disconnected():
    print("iPhone disconnected")


#@app.route("/flagship")
#def flagship():
#    return render_template("flagship.html")
@app.route("/flagship")
def flagship():

    ua = request.headers.get("User-Agent", "")

    if "iPad" in ua and "CPU OS 12_" in ua:
        return send_file("web/flagship_mini2.html")

    return send_file("web/flagship.html")

@app.route("/flagship/current")
def flagship_current():

    try:
        path = current_song()          # <-- Now returns a Path object

        if not path.exists():
            app.logger.error("Audio file not found: %s", path)
            abort(404, description=f"Audio file not found: {path}")

        mimetype = "audio/wav" if path.suffix.lower() == ".wav" else "audio/mpeg"

        file_size = path.stat().st_size
        range_header = request.headers.get("Range")

        if not range_header:
            #app.logger.info(
            #    "Serving %s (%s) with send_file()",
            #    path.name,
            #    mimetype,
            #)
            return send_file(
                path,
                mimetype=mimetype,
                conditional=True,
            )

        start, end = range_header.replace("bytes=", "").split("-")

        start = int(start)
        end = file_size - 1 if end == "" else int(end)

        length = end - start + 1

        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        response = Response(
            data,
            206,
            mimetype=mimetype,
            direct_passthrough=True,
        )

        response.headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Content-Length"] = str(length)

        return response
    except Exception as e:
        app.logger.exception("Error serving %s", path)
        abort(500, description=str(e))

@app.route("/flagship/advance")
def flagship_advance():

    advance_song()

    #app.logger.info("Now playing %s", current_song())

    return ("", 204)

@app.route("/flagship/next")
def flagship_next():
    next_song()
    #app.logger.info("Now playing %s", current_song())
    return ("", 204)

@app.route("/flagship/previous")
def flagship_previous():

    previous_song()

    #app.logger.info("Now playing %s", current_song())

    return ("", 204)

@app.route("/flagship/status")
def flagship_status():

    return {
        "previous": None if _previous_item is None else _previous_item["path"].name,
        "current": None if _current_item is None else _current_item["path"].name,
        "next": None if _next_item is None else _next_item["path"].name,
    }

@app.route("/file-operation-download")
def file_operation_download():

    name = request.args.get("name")

    if not name:
        return "No file selected.", 400

    path = LAN_CLOUD_FOLDER / name

    if not path.exists():
        return "Selected file or directory not found.", 404


    ###########################################################
    # Create Temporary ZIP
    ###########################################################

    temp_zip = tempfile.NamedTemporaryFile(

        suffix=".zip",

        delete=False

    )

    temp_zip.close()

    zip_filename = temp_zip.name


    ###########################################################
    # Build ZIP
    ###########################################################

    with zipfile.ZipFile(

            zip_filename,

            "w",

            compression=zipfile.ZIP_DEFLATED,

            compresslevel=9

    ) as archive:


        #######################################################
        # Selected item is a FILE
        #######################################################

        if path.is_file():

            archive.write(

                path,

                arcname=path.name

            )


        #######################################################
        # Selected item is a DIRECTORY
        #######################################################

        else:

            for root, dirs, files in os.walk(path):

                for filename in files:

                    full_path = Path(root) / filename

                    archive_name = full_path.relative_to(path.parent)

                    archive.write(

                        full_path,

                        arcname=archive_name

                    )


    ###########################################################
    # Delete ZIP after download completes
    ###########################################################

    @after_this_request
    def cleanup(response):

        try:

            os.remove(zip_filename)

        except Exception as e:

            print(e)

        return response


    ###########################################################
    # Download ZIP
    ###########################################################

    return send_file(

        zip_filename,

        as_attachment=True,

        download_name=path.name + ".zip",

        mimetype="application/zip"

    )

@app.route(
    "/file-operation-upload",
    methods=["POST"]
)
def file_operation_upload():

    try:

        uploaded_chunk = request.files["file"]

        filename = request.form["filename"]

        current_directory = request.form[
            "current_directory"
        ]

        chunk_number = int(
            request.form["chunk_number"]
        )

        total_chunks = int(
            request.form["total_chunks"]
        )


        ####################################################
        # Destination Directory
        ####################################################

# If we are in the root shared folder, don't append it again.

        if current_directory == LAN_CLOUD_FOLDER.name:

            destination_directory = LAN_CLOUD_FOLDER

        else:

            destination_directory = (
                LAN_CLOUD_FOLDER /
                current_directory
            )

        destination_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        ####################################################
        # Temporary File
        ####################################################

        temporary_file = (

            UPLOAD_TEMP_FOLDER /

            (filename + ".part")

        )


        ####################################################
        # First Chunk
        ####################################################

        if chunk_number == 0:

            if temporary_file.exists():

                temporary_file.unlink()


        ####################################################
        # Append Chunk
        ####################################################

        with open(

                temporary_file,

                "ab"

        ) as output_file:

            shutil.copyfileobj(

                uploaded_chunk.stream,

                output_file

            )


        ####################################################
        # Last Chunk
        ####################################################

        if chunk_number == total_chunks - 1:

            final_file = (

                destination_directory /

                filename

            )

            temporary_file.replace(

                final_file

            )

            print(

                f"Uploaded : {final_file}"

            )

            BuildLANcloudDirectoryJSON()


        ####################################################
        # Success
        ####################################################

        return jsonify(

            {

                "status": "ok"

            }

        )

    except Exception as exception:

        print(exception)

        return jsonify(

            {

                "status": "error",

                "message": str(exception)

            }

        ), 500

@app.route("/file-operation", methods=["POST"])
def file_operation():

    data = request.get_json()

    operation = data.get("operation")

    selected = data.get("selected", [])

    if operation != "delete":

        return jsonify({

            "status": "error",

            "message": "Unsupported operation."

        })

    deleted = []

    failed = []

    for name in selected:

        path = LAN_CLOUD_FOLDER / name

        try:

            if path.is_dir():

                shutil.rmtree(path)

            elif path.is_file():

                path.unlink()

            else:

                failed.append(name)

                continue

            deleted.append(name)

        except Exception as e:

            failed.append(f"{name} ({e})")

    BuildLANcloudDirectoryJSON()

    return jsonify({

        "status": "ok",

        "deleted": deleted,

        "failed": failed,

        "message":
            f"Deleted {len(deleted)} item(s)."

    })

#@app.route("/LANcloud/list")
#def LANcloudList():
#    return jsonify(LANcloud_JSON)

@app.route("/LANcloud/list")
def LANcloudList():

    folder = request.args.get("folder", "")

    requested = (LAN_CLOUD_FOLDER / folder).resolve()

    #
    # Prevent leaving the shared folder.
    #
    if not str(requested).startswith(str(LAN_CLOUD_FOLDER.resolve())):
        return jsonify({"error": "Access denied"}), 403

    if not requested.exists() or not requested.is_dir():
        return jsonify({"error": "Directory not found"}), 404

    BuildLANcloudDirectoryJSON(requested)

    return jsonify(LANcloud_JSON)

@app.route("/LANcloud")
def LANcloud():

    BuildLANcloudDirectoryJSON()

    print(
        f"[LANcloud] "
        f"{len(LANcloud_JSON['entries'])} entries loaded."
    )

    return render_template("showdirfiles.html")  

@app.route("/LANcloud/change-directory")
def LANcloudChangeDirectory():

    item_id = request.args.get("id")

    if item_id not in LANcloud_ID_MAP:
        return jsonify({"error": "Invalid directory"}), 404

    destination = LANcloud_ID_MAP[item_id]

    if not destination.is_dir():
        return jsonify({"error": "Not a directory"}), 400

    BuildLANcloudDirectoryJSON(destination)

    return jsonify(LANcloud_JSON)

@app.route(
    "/file-operation-new-directory",
    methods=["POST"]
)
def file_operation_new_directory():

    try:

        data = request.get_json()

        current_directory = data[
            "current_directory"
        ]

        directory_name = data[
            "directory_name"
        ].strip()


        #######################################################
        # Basic Validation
        #######################################################

        if (
            "/" in directory_name or
            "\\" in directory_name
        ):

            return jsonify(
            {
                "status":"error",
                "message":
                "Invalid directory name."
            })


        #######################################################
        # Destination
        #######################################################

        if current_directory == "":

            destination = LAN_CLOUD_FOLDER

        else:

            destination = (
                LAN_CLOUD_FOLDER /
                current_directory
            )


        new_directory = (
            destination /
            directory_name
        )


        #######################################################
        # Already Exists
        #######################################################

        if new_directory.exists():

            return jsonify(
            {
                "status":"error",

                "message":
                "Directory already exists."
            })


        #######################################################
        # Create Directory
        #######################################################

        new_directory.mkdir(
            parents=True,
            exist_ok=False
        )

        BuildLANcloudDirectoryJSON(
            destination
        )

        return jsonify(
        {
            "status":"ok",

            "message":
            "Directory created successfully."
        })


    except Exception as e:

        return jsonify(
        {
            "status":"error",

            "message":
            str(e)
        }),500


@socketio.on("clock_time")
def send_clock_time():
    now = datetime.now().astimezone()

    emit(
        "clock_time",
        {
            "timestamp": now.timestamp() * 1000
        }
    )

@app.route("/holiday-today", methods=["GET"])
def holiday_today():

    try:

        answer_text = get_cached_holiday_answer()

        return jsonify({
            "answer": answer_text
        })

    except Exception as e:

        print(
            f"\nHoliday Gemini error: {e}"
        )

        return jsonify({
            "answer":
                "Holiday information unavailable."
        }), 500
@app.route("/clock")
def clock():
    return render_template("clock.html")

@socketio.on("mobile_location")
def mobile_location(data):

    print(
        "Mobile GPS:",
        f"lat={data.get('latitude')}",
        f"lon={data.get('longitude')}",
        f"accuracy={data.get('accuracy')} m"
    )

@app.route("/maps/martin/<path:subpath>")
def martin_proxy(subpath):
    """
    Proxy requests from the HTTPS Flask server to the local
    HTTP Martin server.

    Browser:
        https://192.168.0.25:8000/maps/martin/india/...

    Martin:
        http://127.0.0.1:3000/india/...
    """

    url = f"{MARTIN_URL}/{subpath}"

    try:
        response = requests.get(
            url,
            params=request.args,
            timeout=30
        )

        excluded_headers = {
            "content-encoding",
            "transfer-encoding",
            "connection",
            "content-length"
        }

        headers = [
            (key, value)
            for key, value in response.headers.items()
            if key.lower() not in excluded_headers
        ]

        return Response(
            response.content,
            status=response.status_code,
            headers=headers
        )

    except requests.RequestException as e:

        print(f"Martin proxy error: {e}")

        return Response(
            "Martin server unavailable",
            status=502,
            mimetype="text/plain"
        )
@app.route("/maps")
def maps():
    return render_template("maps.html")


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=8000,
        debug=False,
        ssl_context=(str(server_cert), str(server_key))
    )
    # You can change port if you want, e.g. port=8000
    #app.run(host="0.0.0.0", port=8000, debug=True)
    #app.run(
    #    host="0.0.0.0",          # important so LAN devices can connect
    #    port=8000,
    #   debug=True,
         #ssl_context=("C:/ssl/cert.pem", "C:/ssl/key.pem")  # use forward slashes or raw string
     #    ssl_context=(str(server_cert), str(server_key))
    #)
