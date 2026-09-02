
from app.common import paths
import random
from pathlib import Path
import uuid
from datetime import datetime

LANcloud_ID_MAP = {}
LANcloud_JSON = {}

def BuildLANcloudDirectoryJSON(folder=None):

    global LANcloud_ID_MAP
    global LANcloud_JSON

    if folder is None:
        folder = paths.LAN_CLOUD_FOLDER

    LANcloud_ID_MAP.clear()

    entries = []

    
    ############################################################
    # Parent Directory (..)
    ############################################################

    if folder != paths.LAN_CLOUD_FOLDER:

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

    if folder == paths.LAN_CLOUD_FOLDER:

        current_directory = ""

    else:

        current_directory = str(
            folder.relative_to(paths.LAN_CLOUD_FOLDER)
        )

    ############################################################
    # JSON returned to JavaScript
    ############################################################

    LANcloud_JSON = {

        "command": "directory_listing",

        "current_directory": current_directory,

        "entries": entries
    }
