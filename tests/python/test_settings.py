from fastapi.testclient import TestClient
import pytest
import os
import json

from python_service.app.main import app

def test_settings_load_save():
    client = TestClient(app)
    
    # Save settings
    test_settings = {'mt5_path': 'C:/Metatrader', 'auto_connect': True}
    response = client.post('/settings', json=test_settings)
    assert response.status_code == 200
    
    # Load settings
    response = client.get('/settings')
    assert response.status_code == 200
    loaded = response.json()
    assert loaded['mt5_path'] == 'C:/Metatrader'
    assert loaded['auto_connect'] is True
