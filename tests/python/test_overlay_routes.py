from fastapi.testclient import TestClient
import pytest

from python_service.app.main import app

def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
