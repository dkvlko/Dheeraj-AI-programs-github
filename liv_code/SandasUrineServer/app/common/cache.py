import threading

from app.common.paths import (
    HOLIDAY_CACHE_FILE,
    DATE_DETAILS_CACHE_FILE,
)

from app.config import Config


HOLIDAY_CACHE_LOCK = threading.Lock()

DATE_DETAILS_CACHE_LOCK = threading.Lock()
