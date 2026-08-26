from pathlib import Path

from app.common.paths import AI_KEY_FILE


def load_ai_key() -> str:

    return AI_KEY_FILE.read_text(
        encoding="utf-8"
    ).strip()
