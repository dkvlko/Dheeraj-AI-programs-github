from pathlib import Path


# ------------------------------------------------------------
# Project
# ------------------------------------------------------------

CURRENT_FILE = Path(__file__).resolve()

# app/common/paths.py
# parents[0] = common
# parents[1] = app
# parents[2] = PROJECT_ROOT
PROJECT_ROOT = CURRENT_FILE.parents[2]

PROJECT_ROOT_SSL = PROJECT_ROOT.parent

#External BLOB#
EXT_BLOB = PROJECT_ROOT.parent / "BLOBS"
EXT_BLOB = EXT_BLOB.resolve()
# ------------------------------------------------------------
# Web
# ------------------------------------------------------------

#TEMPLATE_FOLDER = PROJECT_ROOT / "web"

#STATIC_FOLDER = TEMPLATE_FOLDER / "static"


# ------------------------------------------------------------
# Database
# ------------------------------------------------------------

DB_PATH = EXT_BLOB / "SandasServ_BLOB" / "activities.db"


# ------------------------------------------------------------
# AI
# ------------------------------------------------------------

AI_API_DIR = PROJECT_ROOT_SSL / "AI-key"

AI_KEY_FILE = AI_API_DIR / "AI-keys.key"


# ------------------------------------------------------------
# SSL
# ------------------------------------------------------------

CERT_DIR = PROJECT_ROOT_SSL / "sslcert"

#SERVER_CERT = CERT_DIR / "ubuntu_server.crt"
SERVER_CERT = CERT_DIR / "ubuntu_server_192_168_0_25.crt"
#SERVER_KEY = CERT_DIR / "ubuntu_server.key"
SERVER_KEY = CERT_DIR / "ubuntu_server_192_168_0_25.key"



# ------------------------------------------------------------
# Music
# ------------------------------------------------------------

DOWNLOAD_DIR = (
    EXT_BLOB /
    "SpotifyMusicRIP"
)


AD_FILE = "Shaitaan.mp3"

ANNOUNCEMENT_DIR = (
    EXT_BLOB /
    "Announcements"
)

BLOBS_DIR = (
    EXT_BLOB /
    "Temp"
)

PLAYLIST_LOG = (
    BLOBS_DIR /
    "FlagshipPlaylist.log"
)


# ------------------------------------------------------------
# LAN cloud
# ------------------------------------------------------------

LAN_CLOUD_FOLDER = (
    EXT_BLOB /
    "SharedDataOnLan"
)

UPLOAD_TEMP_FOLDER = (
    LAN_CLOUD_FOLDER /
    ".upload_temp"
)


#Open Maps settings
MARTIN_URL = "http://127.0.0.1:3000"

# ------------------------------------------------------------
# Holiday/date caches
# ------------------------------------------------------------

HOLIDAY_CACHE_FILE = (
    EXT_BLOB /
    "SandasServ_BLOB" /
    "holiday_cache.json"
)

DATE_DETAILS_CACHE_FILE = (
    EXT_BLOB /
    "SandasServ_BLOB" /
    "date_details_cache.json"
)
