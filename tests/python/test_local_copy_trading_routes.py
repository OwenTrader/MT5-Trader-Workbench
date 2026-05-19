from fastapi import FastAPI
from fastapi.testclient import TestClient

from python_service.app.local_copy_trading import routes as local_copy_trading_routes
from python_service.app.local_copy_trading.routes import router as local_copy_trading_router
from python_service.app.local_copy_trading.runtime import reset_state


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
    assert 'source_accounts' in response.json()
    assert 'follower_accounts' in response.json()
    assert 'relationships' in response.json()
    assert 'events' in response.json()


def test_create_source_account_route_persists_payload(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    response = client.post('/local-copy-trading/source-accounts', json={
        'name': 'Main A',
        'connection_type': 'simulated',
        'terminal_path': '',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })

    assert response.status_code == 200
    assert response.json()['source_accounts'][0]['name'] == 'Main A'


def test_create_follower_account_route_persists_payload(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    response = client.post('/local-copy-trading/follower-accounts', json={
        'name': 'Follower A',
        'connection_type': 'simulated',
        'terminal_path': '',
        'login': '2001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })

    assert response.status_code == 200
    assert response.json()['follower_accounts'][0]['name'] == 'Follower A'


def test_create_relationship_route_persists_payload(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    client.post('/local-copy-trading/source-accounts', json={
        'id': 'src-1',
        'name': 'Main A',
        'connection_type': 'simulated',
        'terminal_path': '',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })
    client.post('/local-copy-trading/follower-accounts', json={
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
        'lot_multiplier': 1,
        'is_active': True,
    })

    assert response.status_code == 200
    assert response.json()['relationships'][0]['symbol'] == 'XAUUSD'


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


def test_update_runtime_route_persists_enabled_and_poll_interval(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    client.post('/local-copy-trading/source-accounts', json={
        'id': 'src-1',
        'name': 'Main A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'C:/MT5/terminal64.exe',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })
    client.post('/local-copy-trading/follower-accounts', json={
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
    assert 'Add at least 1 source account' in response.json()['detail']


def test_update_runtime_route_rejects_invalid_payload(tmp_path, monkeypatch):
    reset_state()
    app = build_test_app()
    client = TestClient(app)

    response = client.post('/local-copy-trading/runtime', json={
        'enabled': 'not-a-bool',
        'poll_interval_seconds': 'not-a-number',
    })

    assert response.status_code == 422


def test_create_source_account_route_rejects_invalid_mt5_credentials(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (False, 'MT5 credential verification failed'))
    app = build_test_app()
    client = TestClient(app)

    response = client.post('/local-copy-trading/source-accounts', json={
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


def test_delete_source_account_route_removes_account_and_relationships(tmp_path, monkeypatch):
    reset_state()
    monkeypatch.setattr(local_copy_trading_routes, 'verify_mt5_credentials', lambda **kwargs: (True, None))
    app = build_test_app()
    client = TestClient(app)

    client.post('/local-copy-trading/source-accounts', json={
        'id': 'src-1',
        'name': 'Main A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'C:/MT5/terminal64.exe',
        'login': '1001',
        'server': 'demo',
        'password': 'secret',
        'is_active': True,
    })
    client.post('/local-copy-trading/follower-accounts', json={
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

    response = client.delete('/local-copy-trading/source-accounts/src-1')

    assert response.status_code == 200
    assert response.json()['source_accounts'] == []
    assert response.json()['relationships'] == []
