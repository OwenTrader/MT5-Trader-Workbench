from fastapi import APIRouter, HTTPException

from python_service.app.services.storage_paths import overlay_config_file
from pydantic import BaseModel, Field
import json
import os

router = APIRouter()

class OverlayToggle(BaseModel):
    visible: bool

class OverlayCoordinates(BaseModel):
    x: int
    y: int

class OverlayImportPayload(BaseModel):
    """Imported overlay configs are user files; keep them bounded and typed
    instead of writing an arbitrary dict straight to disk."""
    name: str = Field(default='Default', max_length=100)
    alerts: list[dict] = Field(default_factory=list, max_length=200)

# Simple global state for now
_overlay_state = {
    'is_visible': False,
    'x': 100,
    'y': 100
}

@router.get('/overlay/status')
def get_overlay_status():
    return _overlay_state

@router.post('/overlay/toggle')
def toggle_overlay(toggle: OverlayToggle):
    _overlay_state['is_visible'] = toggle.visible
    return _overlay_state

@router.post('/overlay/coordinates')
def update_coordinates(coords: OverlayCoordinates):
    _overlay_state['x'] = coords.x
    _overlay_state['y'] = coords.y
    return _overlay_state

@router.get('/overlay/export')
def export_overlay():
    if overlay_config_file().exists():
        with open(overlay_config_file(), 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'name': 'Default', 'alerts': []}

@router.post('/overlay/import')
def import_overlay(payload: OverlayImportPayload):
    overlay_config_file().parent.mkdir(parents=True, exist_ok=True)
    if len(json.dumps(payload.model_dump(), ensure_ascii=False)) > 100_000:
        raise HTTPException(status_code=413, detail='Overlay config too large')
    with open(overlay_config_file(), 'w', encoding='utf-8') as f:
        json.dump(payload.model_dump(), f, ensure_ascii=False, indent=2)
    return {'status': 'ok'}
