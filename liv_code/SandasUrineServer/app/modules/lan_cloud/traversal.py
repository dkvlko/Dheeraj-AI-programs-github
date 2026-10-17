import json
import os
import threading
from pathlib import Path

from app.common import paths


MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
TRAVERSAL_FILE = DATA_DIR / "traversal.json"

_LOCK = threading.RLock()


def get_root():
    return paths.LAN_CLOUD_FOLDER.resolve()


def resolve_path(relative_path=""):
    if not isinstance(relative_path, str):
        raise ValueError("Directory path must be a string.")

    root = get_root()
    target = (root / relative_path).resolve()

    if not target.is_relative_to(root):
        raise PermissionError("Access denied.")

    return target


def save_current_directory(relative_path):
    with _LOCK:
        directory = resolve_path(relative_path)

        if not directory.is_dir():
            raise NotADirectoryError(
                "Directory does not exist."
            )

        root = get_root()

        normalized = (
            ""
            if directory == root
            else directory.relative_to(root).as_posix()
        )

        DATA_DIR.mkdir(parents=True, exist_ok=True)

        temporary_file = TRAVERSAL_FILE.with_suffix(".tmp")

        try:
            with temporary_file.open(
                "w", encoding="utf-8"
            ) as file:
                json.dump(
                    {"current_directory": normalized},
                    file,
                    indent=2
                )
                file.flush()
                os.fsync(file.fileno())

            temporary_file.replace(TRAVERSAL_FILE)

        finally:
            if temporary_file.exists():
                temporary_file.unlink()

        return normalized


def get_current_directory():
    with _LOCK:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if not TRAVERSAL_FILE.exists():
            return save_current_directory("")

        try:
            with TRAVERSAL_FILE.open(
                "r", encoding="utf-8"
            ) as file:
                data = json.load(file)

            relative_path = data["current_directory"]

            if not isinstance(relative_path, str):
                raise ValueError("Invalid directory record.")

            directory = resolve_path(relative_path)

            if not directory.is_dir():
                raise ValueError("Directory no longer exists.")

            root = get_root()

            return (
                ""
                if directory == root
                else directory.relative_to(root).as_posix()
            )

        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            PermissionError,
        ):
            return save_current_directory("")
