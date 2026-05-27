from fastapi.testclient import TestClient
import pytest
import os
import json
from pathlib import Path

from python_service.app.main import app
from python_service.app.routes import settings as settings_route


def test_settings_load_save(tmp_path, monkeypatch):
    settings_file = tmp_path / 'settings.local.json'
    default_settings_file = tmp_path / 'settings.default.json'
    default_settings_file.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(settings_route, 'SETTINGS_FILE', Path(settings_file))
    monkeypatch.setattr(settings_route, 'DEFAULT_SETTINGS_FILE', Path(default_settings_file))

    client = TestClient(app)
    
    # Save settings
    test_settings = {
        'mt5_path': 'C:/Metatrader',
        'ai_base_url': 'https://example.test/v1',
        'ai_api_key': 'sk-test',
        'ai_model': 'gpt-4o-mini',
        'ai_timeframe': 'H1',
        'ai_candles_count': 120,
        'ai_temperature': 0.4,
        'ai_system_prompt': 'Focus on trend continuation.',
        'auto_connect': True,
    }
    response = client.post('/settings', json=test_settings)
    assert response.status_code == 200
    
    # Load settings
    response = client.get('/settings')
    assert response.status_code == 200
    loaded = response.json()
    assert loaded['mt5_path'] == 'C:/Metatrader'
    assert loaded['ai_base_url'] == 'https://example.test/v1'
    assert loaded['ai_api_key'] == 'sk-test'
    assert loaded['ai_model'] == 'gpt-4o-mini'
    assert loaded['ai_timeframe'] == 'H1'
    assert loaded['ai_candles_count'] == 120
    assert loaded['ai_temperature'] == 0.4
    assert loaded['ai_system_prompt'] == 'Focus on trend continuation.'
    assert loaded['auto_connect'] is True
