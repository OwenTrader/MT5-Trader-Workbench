import json
import logging
import os
import threading
from pathlib import Path

from fastapi import APIRouter

from python_service.app.models.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter()
SETTINGS_FILE = Path(os.environ.get('SETTINGS_FILE', 'storage/settings.local.json'))
DEFAULT_SETTINGS_FILE = Path(os.environ.get('DEFAULT_SETTINGS_FILE', 'storage/settings.default.json'))

# get_settings sits on the hottest path in the app (every MT5 client call,
# every streaming tick, every notification). Parsing the file each time is
# waste; cache the parsed model and invalidate on mtime change or save.
_cache_lock = threading.Lock()
_cached_settings: Settings | None = None
_cached_mtime: float | None = None
_cached_size: int | None = None


def ensure_storage():
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)


def ensure_settings_file() -> None:
    ensure_storage()

    if SETTINGS_FILE.exists():
        return

    if DEFAULT_SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(DEFAULT_SETTINGS_FILE.read_text(encoding='utf-8'), encoding='utf-8')


def _settings_stamp() -> tuple[float, int] | None:
    try:
        stat = SETTINGS_FILE.stat()
        return stat.st_mtime, stat.st_size
    except OSError:
        return None


def invalidate_settings_cache() -> None:
    global _cached_settings, _cached_mtime, _cached_size
    with _cache_lock:
        _cached_settings = None
        _cached_mtime = None
        _cached_size = None


@router.get('/settings')
def get_settings() -> Settings:
    global _cached_settings, _cached_mtime, _cached_size

    ensure_settings_file()

    stamp = _settings_stamp()
    if stamp is None:
        return Settings()

    with _cache_lock:
        if _cached_settings is not None and (_cached_mtime, _cached_size) == stamp:
            return _cached_settings

    try:
        with SETTINGS_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f)
        parsed = Settings(**data)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        logger.warning('Failed to load settings from %s (%s); falling back to defaults', SETTINGS_FILE, error)
        return Settings()

    with _cache_lock:
        _cached_settings = parsed
        _cached_mtime, _cached_size = stamp
    return parsed


@router.post('/settings')
def save_settings(settings: Settings) -> dict[str, str]:
    ensure_storage()
    # Atomic write so a crash mid-save cannot leave a truncated settings file.
    temp_path = SETTINGS_FILE.with_suffix('.tmp')
    temp_path.write_text(json.dumps(settings.model_dump(), ensure_ascii=False, indent=2), encoding='utf-8')
    temp_path.replace(SETTINGS_FILE)
    invalidate_settings_cache()
    return {'status': 'ok'}
