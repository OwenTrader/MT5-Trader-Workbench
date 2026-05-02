from fastapi import APIRouter
from pydantic import BaseModel
import json
import os

router = APIRouter()

class OverlayToggle(BaseModel):
    visible: bool

class OverlayCoordinates(BaseModel):
    x: int
    y: int

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
    if os.path.exists('storage/overlay_config.json'):
        with open('storage/overlay_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'name': 'Default', 'alerts': []}

@router.post('/overlay/import')
def import_overlay(config: dict):
    os.makedirs('storage', exist_ok=True)
    with open('storage/overlay_config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return {'status': 'ok'}
