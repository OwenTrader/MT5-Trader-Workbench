from fastapi.testclient import TestClient
import pytest

from python_service.app.main import app

def test_overlay_status_endpoint():
    client = TestClient(app)
    response = client.get('/overlay/status')
    assert response.status_code == 200
    assert 'is_visible' in response.json()

def test_overlay_toggle_endpoint():
    client = TestClient(app)
    response = client.post('/overlay/toggle', json={'visible': True})
    assert response.status_code == 200
    assert response.json()['is_visible'] is True
    
    response = client.post('/overlay/toggle', json={'visible': False})
    assert response.status_code == 200
    assert response.json()['is_visible'] is False
