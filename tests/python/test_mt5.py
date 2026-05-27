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

    with patch('python_service.app.routes.mt5.init_mt5', return_value=False):
        response = client.post('/mt5/launch')

    assert response.status_code == 200
    assert response.json()['status'] == 'error'


def test_account_endpoint_does_not_allow_launch_by_default(monkeypatch):
    seen = {}

    def fake_get_account_info(*, allow_launch=True):
        seen['allow_launch'] = allow_launch
        return {}

    monkeypatch.setattr('python_service.app.routes.mt5.get_account_info', fake_get_account_info)
    client = TestClient(app)

    response = client.get('/mt5/account')

    assert response.status_code == 200
    assert seen['allow_launch'] is False


def test_positions_endpoint_does_not_allow_launch_by_default(monkeypatch):
    seen = {}

    def fake_get_positions(*, allow_launch=True):
        seen['allow_launch'] = allow_launch
        return []

    monkeypatch.setattr('python_service.app.routes.mt5.get_positions', fake_get_positions)
    client = TestClient(app)

    response = client.get('/mt5/positions')

    assert response.status_code == 200
    assert seen['allow_launch'] is False


def test_verify_path_endpoint_uses_dedicated_path_verification(monkeypatch):
    seen = {}

    def fake_verify_mt5_path_connection(path: str):
        seen['path'] = path
        return True, None, {'path': path}

    monkeypatch.setattr('python_service.app.routes.mt5.verify_mt5_path_connection', fake_verify_mt5_path_connection)
    client = TestClient(app)

    response = client.post('/mt5/verify_path', json={'path': 'C:/MT5/terminal64.exe'})

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'
    assert response.json()['terminal_info'] == {'path': 'C:/MT5/terminal64.exe'}
    assert seen['path'] == 'C:/MT5/terminal64.exe'
