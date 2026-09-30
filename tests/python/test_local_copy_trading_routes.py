import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python_service.app.local_copy_trading import copy_trading_db, routes as local_copy_trading_routes
from python_service.app.local_copy_trading.routes import router as local_copy_trading_router
from python_service.app.local_copy_trading.runtime import reset_state


@pytest.fixture(autouse=True)
def _isolate_storage(tmp_path, monkeypatch):
    """Keep runtime storage (state json, order-map db, risk settings) out of the repo."""
    monkeypatch.chdir(tmp_path)


def build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(local_copy_trading_router)
    return app


def test_get_overview_returns_local_copy_payload(tmp_path, monkeypatch):
    reset_state()
    app = build_test_app()
    client = TestClient(app)

    response = client.get('/local-copy-trading')

    assert response.status_code == 200
    assert 'accounts' in response.json()
    assert 'relationships' in response.json()
    assert 'events' in response.json()


def test_create_account_route_persists_payload(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    response = client.post('/local-copy-trading/accounts', json={
        'name': 'Main A',
        'connection_type': 'simulated',
        'terminal_path': '',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })

    assert response.status_code == 200
    assert response.json()['accounts'][0]['name'] == 'Main A'


def test_update_account_route_persists_payload(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    client.post('/local-copy-trading/accounts', json={
        'id': 'src-1',
        'name': 'Main A',
        'connection_type': 'simulated',
        'terminal_path': '',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })

    response = client.put('/local-copy-trading/accounts/src-1', json={
        'name': 'Main A Updated',
        'connection_type': 'simulated',
        'terminal_path': 'C:/MT5/source/terminal64.exe',
        'login': '1002',
        'server': 'demo-2',
        'password': 'secret-2',
        'is_active': True,
    })

    assert response.status_code == 200
    assert response.json()['accounts'][0]['id'] == 'src-1'
    assert response.json()['accounts'][0]['name'] == 'Main A Updated'


def test_create_relationship_route_persists_payload(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    client.post('/local-copy-trading/accounts', json={
        'id': 'src-1',
        'name': 'Main A',
        'connection_type': 'simulated',
        'terminal_path': '',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })
    client.post('/local-copy-trading/accounts', json={
        'id': 'fol-1',
        'name': 'Follower A',
        'connection_type': 'simulated',
        'terminal_path': '',
        'login': '2001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })

    response = client.post('/local-copy-trading/relationships', json={
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'symbol': 'XAUUSD',
        'source_symbol': 'XAUUSD',
        'follower_symbol': 'XAUUSD.m',
        'lot_multiplier': 1,
        'is_active': True,
    })

    assert response.status_code == 200
    assert response.json()['relationships'][0]['symbol'] == 'XAUUSD'
    assert response.json()['relationships'][0]['source_symbol'] == 'XAUUSD'
    assert response.json()['relationships'][0]['follower_symbol'] == 'XAUUSD.m'


def test_create_relationship_route_rejects_unknown_accounts(tmp_path, monkeypatch):
    reset_state()
    app = build_test_app()
    client = TestClient(app)

    response = client.post('/local-copy-trading/relationships', json={
        'source_account_id': 'missing-source',
        'follower_account_id': 'missing-follower',
        'symbol': 'XAUUSD',
        'lot_multiplier': 1,
        'is_active': True,
    })

    assert response.status_code == 400


def test_create_relationship_route_rejects_same_account_for_both_roles(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    client.post('/local-copy-trading/accounts', json={
        'id': 'acc-1',
        'name': 'Main A',
        'connection_type': 'simulated',
        'terminal_path': '',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })

    response = client.post('/local-copy-trading/relationships', json={
        'source_account_id': 'acc-1',
        'follower_account_id': 'acc-1',
        'symbol': 'XAUUSD',
        'lot_multiplier': 1,
        'is_active': True,
    })

    assert response.status_code == 400
    assert response.json()['detail'] == 'Source and follower accounts must be different'


def test_create_relationship_route_accepts_new_symbol_mapping_fields_without_legacy_symbol(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    client.post('/local-copy-trading/accounts', json={
        'id': 'src-1',
        'name': 'Main A',
        'connection_type': 'simulated',
        'terminal_path': '',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })
    client.post('/local-copy-trading/accounts', json={
        'id': 'fol-1',
        'name': 'Follower A',
        'connection_type': 'simulated',
        'terminal_path': '',
        'login': '2001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })

    response = client.post('/local-copy-trading/relationships', json={
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'source_symbol': 'XAUUSD',
        'follower_symbol': 'XAUUSD.m',
        'lot_multiplier': 1,
        'is_active': True,
    })

    assert response.status_code == 200
    assert response.json()['relationships'][0]['symbol'] == 'XAUUSD'
    assert response.json()['relationships'][0]['source_symbol'] == 'XAUUSD'
    assert response.json()['relationships'][0]['follower_symbol'] == 'XAUUSD.m'


def test_update_runtime_route_persists_enabled_and_poll_interval(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    client.post('/local-copy-trading/accounts', json={
        'id': 'src-1',
        'name': 'Main A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'C:/MT5/terminal64.exe',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })
    client.post('/local-copy-trading/accounts', json={
        'id': 'fol-1',
        'name': 'Follower A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'D:/MT5/terminal64.exe',
        'login': '2001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })
    client.post('/local-copy-trading/relationships', json={
        'id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'symbol': 'XAUUSD',
        'lot_multiplier': 1,
        'is_active': True,
    })

    response = client.post('/local-copy-trading/runtime', json={
        'enabled': True,
        'poll_interval_seconds': 3,
    })

    assert response.status_code == 200
    assert response.json()['runtime']['enabled'] is True
    assert response.json()['runtime']['poll_interval_seconds'] == 3


def test_update_runtime_route_rejects_enable_without_complete_configuration(tmp_path, monkeypatch):
    reset_state()
    app = build_test_app()
    client = TestClient(app)

    response = client.post('/local-copy-trading/runtime', json={
        'enabled': True,
    })

    assert response.status_code == 400
    assert 'Add at least 2 accounts' in response.json()['detail']


def test_update_runtime_route_rejects_invalid_payload(tmp_path, monkeypatch):
    reset_state()
    app = build_test_app()
    client = TestClient(app)

    response = client.post('/local-copy-trading/runtime', json={
        'enabled': 'not-a-bool',
        'poll_interval_seconds': 'not-a-number',
    })

    assert response.status_code == 422


def test_create_account_route_rejects_invalid_mt5_credentials(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (False, 'MT5 credential verification failed'))
    app = build_test_app()
    client = TestClient(app)

    response = client.post('/local-copy-trading/accounts', json={
        'name': 'Main A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'C:/MT5/terminal64.exe',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })

    assert response.status_code == 400
    assert response.json()['detail'] == 'MT5 credential verification failed'


def test_delete_account_route_removes_account_and_relationships(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    client.post('/local-copy-trading/accounts', json={
        'id': 'src-1',
        'name': 'Main A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'C:/MT5/terminal64.exe',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })
    client.post('/local-copy-trading/accounts', json={
        'id': 'fol-1',
        'name': 'Follower A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'D:/MT5/terminal64.exe',
        'login': '2001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })
    client.post('/local-copy-trading/relationships', json={
        'id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'symbol': 'XAUUSD',
        'lot_multiplier': 1,
        'is_active': True,
    })

    response = client.delete('/local-copy-trading/accounts/src-1')

    assert response.status_code == 200
    assert response.json()['accounts'] == [
        {
            'id': 'fol-1',
            'name': 'Follower A',
            'connection_type': 'mt5_terminal',
            'terminal_path': 'D:/MT5/terminal64.exe',
            'login': '2001',
            'server': 'demo',
            'password': 'secret',
            'is_active': True,
        },
    ]
    assert response.json()['relationships'] == []


def _seed_two_accounts_and_relationship(client):
    for account_id, name, login in (('src-1', 'Main A', '1001'), ('fol-1', 'Follower A', '2001')):
        client.post('/local-copy-trading/accounts', json={
            'id': account_id,
            'name': name,
            'connection_type': 'simulated',
            'terminal_path': '',
            'login': login,
            'server': 'demo',
            'password': 'secret',
            'is_active': True,
        })
    client.post('/local-copy-trading/relationships', json={
        'id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'symbol': 'XAUUSD',
        'lot_multiplier': 1,
        'is_active': True,
    })


def test_risk_settings_default_to_disabled_limits(tmp_path, monkeypatch):
    reset_state()
    app = build_test_app()
    client = TestClient(app)

    response = client.get('/local-copy-trading/risk-settings')

    assert response.status_code == 200
    assert response.json() == {
        'max_volume_per_symbol': 0,
        'max_positions_per_symbol': 0,
        'max_daily_open_count': 0,
        'max_daily_loss': 0,
        'min_margin_level': 0,
        'max_consecutive_failures': 3,
    }


def test_risk_settings_roundtrip_through_the_api(tmp_path, monkeypatch):
    reset_state()
    app = build_test_app()
    client = TestClient(app)
    payload = {
        'max_volume_per_symbol': 2.5,
        'max_positions_per_symbol': 4,
        'max_daily_open_count': 10,
        'max_daily_loss': 500,
        'min_margin_level': 150,
        'max_consecutive_failures': 2,
    }

    put_response = client.put('/local-copy-trading/risk-settings', json=payload)
    get_response = client.get('/local-copy-trading/risk-settings')

    assert put_response.status_code == 200
    assert put_response.json() == payload
    assert get_response.json() == payload


def test_risk_settings_reject_negative_limits(tmp_path, monkeypatch):
    reset_state()
    app = build_test_app()
    client = TestClient(app)

    response = client.put('/local-copy-trading/risk-settings', json={'max_daily_loss': -100})

    assert response.status_code == 422


def test_delete_relationship_route_cleans_the_order_map(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)
    _seed_two_accounts_and_relationship(client)
    copy_trading_db.init_db()
    copy_trading_db.insert_pending(
        client_key='rel-1:pos-1',
        relationship_id='rel-1',
        source_account_id='src-1',
        follower_account_id='fol-1',
        source_position_id='pos-1',
        created_at='2026-09-18T00:00:00+00:00',
    )

    response = client.delete('/local-copy-trading/relationships/rel-1')

    assert response.status_code == 200
    assert copy_trading_db.find_by_client_key('rel-1:pos-1') is None


def test_delete_account_route_cleans_the_order_map(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)
    _seed_two_accounts_and_relationship(client)
    copy_trading_db.init_db()
    copy_trading_db.insert_pending(
        client_key='rel-1:pos-1',
        relationship_id='rel-1',
        source_account_id='src-1',
        follower_account_id='fol-1',
        source_position_id='pos-1',
        created_at='2026-09-18T00:00:00+00:00',
    )

    response = client.delete('/local-copy-trading/accounts/src-1')

    assert response.status_code == 200
    assert copy_trading_db.find_by_client_key('rel-1:pos-1') is None
