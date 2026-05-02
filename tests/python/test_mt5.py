from fastapi.testclient import TestClient
import pytest
from unittest.mock import patch

from python_service.app.main import app

def test_mt5_status_endpoint():
    client = TestClient(app)
    response = client.get('/mt5/status')
    assert response.status_code == 200
    assert 'is_running' in response.json()

def test_mt5_launch_no_path():
    client = TestClient(app)
    # Clear settings first
    client.post('/settings', json={'mt5_path': ''})
    
    response = client.post('/mt5/launch')
    assert response.status_code == 200
    assert response.json()['status'] == 'error'
