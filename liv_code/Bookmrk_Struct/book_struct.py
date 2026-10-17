#!/usr/bin/env python3
"""
Firefox Bookmarks → HTML Folder Exporter
Python 3.14

Features:
- Reads Firefox bookmarks from places.sqlite
- Preserves full bookmark folder hierarchy
- Creates actual Linux directories
- Creates index.html inside every directory
- Clickable links work on:
    - Ubuntu
    - iPhone
    - Safari
    - Chrome
    - Firefox
    - iCloud Drive / Google Drive
- Skips duplicate URLs inside same folder
- Unicode/Hindi safe

Output:
~/FirefoxBookmarks/
"""

import sqlite3
import shutil
import html
import re
from pathlib import Path
from collections import defaultdict

# =========================================================
# CONFIG
# =========================================================

OUTPUT_DIR = Path.home() / "FirefoxBookmarks"

# Firefox bookmark roots
ROOT_IDS = {1, 2, 3, 4, 5}

# =========================================================
# HELPERS
# =========================================================

def sanitize_filename(name: str) -> str:
    """
    Linux-safe filenames.
    """
    if not name:
        return "Unnamed"

    name = re.sub(r'[<>:"/\\|?*\n\r\t]', '_', name)
    name = name.strip()

    if not name:
        name = "Unnamed"

    return name[:150]


def html_escape(text: str) -> str:
    return html.escape(text or "")


# =========================================================
# FIND FIREFOX PROFILE
# =========================================================

#firefox_dir = Path.home() / ".mozilla" / "firefox"

#profiles = sorted(firefox_dir.glob("*.default*"))

#if not profiles:
#    raise SystemExit("No Firefox profile found.")

#profile_dir = profiles[0]

#places_db = profile_dir / "places.sqlite"

#if not places_db.exists():
 #   raise SystemExit("places.sqlite not found.")
profile_dir = Path(
    "/home/dkvlko/.config/mozilla/firefox/tczigzbi.default-release-2"
)

places_db = profile_dir / "places.sqlite"

if not places_db.exists():
    raise SystemExit("places.sqlite not found.")

# =========================================================
# COPY SQLITE DB
# =========================================================

temp_db = Path("/tmp/firefox_places.sqlite")

shutil.copy2(places_db, temp_db)

# =========================================================
# CONNECT SQLITE
# =========================================================

conn = sqlite3.connect(temp_db)
cursor = conn.cursor()

# =========================================================
# LOAD BOOKMARK STRUCTURE
# =========================================================

cursor.execute("""
SELECT
    id,
    parent,
    title,
    type,
    fk
FROM moz_bookmarks
""")

bookmarks = cursor.fetchall()

# type:
# 1 = bookmark
# 2 = folder

# ---------------------------------------------------------

cursor.execute("""
SELECT
    id,
    url
FROM moz_places
""")

url_map = {row[0]: row[1] for row in cursor.fetchall()}

# =========================================================
# BUILD TREE
# =========================================================

nodes = {}

children = defaultdict(list)

for row in bookmarks:
    bid, parent, title, btype, fk = row

    nodes[bid] = {
        "id": bid,
        "parent": parent,
        "title": title or "Unnamed",
        "type": btype,
        "fk": fk,
    }

    children[parent].append(bid)

# =========================================================
# EXPORT
# =========================================================

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

exported_links = 0
created_dirs = 0


def export_folder(folder_id: int, current_path: Path):
    global exported_links
    global created_dirs

    folder_node = nodes.get(folder_id)

    if folder_node:
        folder_name = sanitize_filename(folder_node["title"])

        # Avoid ugly root names
        if folder_id not in ROOT_IDS:
            current_path = current_path / folder_name
            current_path.mkdir(parents=True, exist_ok=True)
            created_dirs += 1

    links_html = []
    seen_urls = set()

    for child_id in children.get(folder_id, []):

        node = nodes[child_id]

        # -----------------------------------------
        # SUBFOLDER
        # -----------------------------------------
        if node["type"] == 2:
            export_folder(child_id, current_path)

        # -----------------------------------------
        # BOOKMARK
        # -----------------------------------------
        elif node["type"] == 1:

            fk = node["fk"]

            if fk not in url_map:
                continue

            url = url_map[fk]

            if not url:
                continue

            # Skip duplicates inside folder
            if url in seen_urls:
                continue

            seen_urls.add(url)

            title = html_escape(node["title"])

            links_html.append(
                f'<li><a href="{html_escape(url)}" '
                f'target="_blank">{title}</a></li>'
            )

            exported_links += 1

    # -----------------------------------------------------
    # CREATE index.html
    # -----------------------------------------------------

    if links_html:

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Bookmarks</title>
<style>
body {{
    font-family: sans-serif;
    margin: 40px;
}}

a {{
    text-decoration: none;
}}

li {{
    margin-bottom: 8px;
}}
</style>
</head>
<body>

<h2>Bookmarks</h2>

<ul>
{chr(10).join(links_html)}
</ul>

</body>
</html>
"""

        index_file = current_path / "index.html"

        if not index_file.exists():
            index_file.write_text(
                html_content,
                encoding="utf-8"
            )


# =========================================================
# START EXPORT
# =========================================================

for root_id in ROOT_IDS:
    export_folder(root_id, OUTPUT_DIR)

# =========================================================
# CLEANUP
# =========================================================

conn.close()

if temp_db.exists():
    temp_db.unlink()

# =========================================================
# DONE
# =========================================================

print()
print("====================================")
print("Firefox bookmarks exported")
print("====================================")
print(f"Directories created : {created_dirs}")
print(f"Bookmarks exported  : {exported_links}")
print()
print(f"Output directory:")
print(OUTPUT_DIR)
print()
