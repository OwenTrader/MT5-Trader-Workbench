from fastapi.testclient import TestClient
import pytest

from python_service.app.main import app
from python_service.app.routes import alerts as alerts_routes


@pytest.fixture(autouse=True)
def reset_order_broadcast_state(tmp_path, monkeypatch):
    monkeypatch.setattr(alerts_routes, 'ALERTS_FILE', str(tmp_path / 'alerts.json'))
    alerts_routes.active_alerts = []
    yield
    alerts_routes.active_alerts = []


def test_add_order_broadcast_rule_rejects_duplicate_symbol_case_insensitively():
    client = TestClient(app)

    first_response = client.post('/alerts/order-broadcast', json={
        'id': '',
        'symbol': ' xauusd ',
        'is_active': True,
    })

    assert first_response.status_code == 200

    rules_response = client.get('/alerts/order-broadcast')
    assert rules_response.status_code == 200
    assert rules_response.json() == [
        {
            'id': first_response.json()['id'],
            'symbol': 'XAUUSD',
            'is_active': True,
        }
    ]

    duplicate_response = client.post('/alerts/order-broadcast', json={
        'id': '',
        'symbol': 'XAUUSD',
        'is_active': True,
    })

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {'detail': {'code': 'duplicate_symbol'}}


def test_update_order_broadcast_rule_rejects_duplicate_symbol_case_insensitively():
    client = TestClient(app)

    first_response = client.post('/alerts/order-broadcast', json={
        'id': '',
        'symbol': 'XAUUSD',
        'is_active': True,
    })
    second_response = client.post('/alerts/order-broadcast', json={
        'id': '',
        'symbol': 'EURUSD',
        'is_active': False,
    })

    update_response = client.put(
        f"/alerts/order-broadcast/{second_response.json()['id']}",
        json={
            'id': second_response.json()['id'],
            'symbol': ' xauusd ',
            'is_active': False,
        },
    )

    assert update_response.status_code == 409
    assert update_response.json() == {'detail': {'code': 'duplicate_symbol'}}

    rules_response = client.get('/alerts/order-broadcast')
    assert rules_response.status_code == 200
    assert rules_response.json() == [
        {
            'id': first_response.json()['id'],
            'symbol': 'XAUUSD',
            'is_active': True,
        },
        {
            'id': second_response.json()['id'],
            'symbol': 'EURUSD',
            'is_active': False,
        },
    ]
