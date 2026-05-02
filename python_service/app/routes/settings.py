from fastapi import APIRouter
from python_service.app.models.settings import Settings
import json
import os
from pathlib import Path

router = APIRouter()
SETTINGS_FILE = Path(os.environ.get('SETTINGS_FILE', 'storage/settings.local.json'))
DEFAULT_SETTINGS_FILE = Path(os.environ.get('DEFAULT_SETTINGS_FILE', 'storage/settings.default.json'))

def ensure_storage():
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

def ensure_settings_file() -> None:
    ensure_storage()

    if SETTINGS_FILE.exists():
        return

    if DEFAULT_SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(DEFAULT_SETTINGS_FILE.read_text(encoding='utf-8'), encoding='utf-8')

@router.get('/settings')
def get_settings() -> Settings:
    ensure_settings_file()

    if SETTINGS_FILE.exists():
        with SETTINGS_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f)
            return Settings(**data)
    return Settings()

@router.post('/settings')
def save_settings(settings: Settings) -> dict[str, str]:
    ensure_storage()
    with SETTINGS_FILE.open('w', encoding='utf-8') as f:
        json.dump(settings.model_dump(), f, ensure_ascii=False, indent=2)
    return {'status': 'ok'}
