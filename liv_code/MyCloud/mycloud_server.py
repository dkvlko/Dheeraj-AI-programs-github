from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from pathlib import Path
import os

app = FastAPI()

# Root directory of your cloud
CLOUD_ROOT = Path("/mnt/elements")

# Simple token (change this!)
AUTH_TOKEN = "mysecrettoken"


def authenticate(authorization: str):
    if not authorization or authorization != f"Bearer {AUTH_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/files")
def list_files(path: str = "", authorization: str = Header(None)):
    authenticate(authorization)

    target_path = (CLOUD_ROOT / path).resolve()

    # Security check: prevent path traversal
    if not str(target_path).startswith(str(CLOUD_ROOT)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Path not found")

    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail="Not a directory")

    items = []

    for item in os.listdir(target_path):
        item_path = target_path / item
        items.append({
            "name": item,
            "type": "folder" if item_path.is_dir() else "file",
            "size": item_path.stat().st_size
        })

    return JSONResponse(content={
        "path": str(target_path.relative_to(CLOUD_ROOT)),
        "items": items
    })
