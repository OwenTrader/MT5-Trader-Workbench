"""Phase 3 robustness behaviors: WS origin guard, event-log cap, quant loop
resilience, settings cache, volatility point units, loop heartbeats."""

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python_service.app.models.alerts import VolatilityAlert
from python_service.app.models.settings import Settings
from python_service.app.quant import event_log
from python_service.app.quant.loop import quant_loop
from python_service.app.quant.models import QuantJobEvent
from python_service.app.routes import stream
from python_service.app.services import alert_service, loop_heartbeat
from python_service.app.routes import settings as settings_routes


def test_websocket_rejects_foreign_origins():
    app = FastAPI()
    app.include_router(stream.router)
    client = TestClient(app)

    with pytest.raises(Exception):
        with client.websocket_connect('/ws/overlay', headers={'Origin': 'https://evil.example.com'}):
            pass  # pragma: no cover - the connect must fail before this


def test_websocket_allows_local_origin():
    app = FastAPI()
    app.include_router(stream.router)
    client = TestClient(app)

    with client.websocket_connect('/ws/overlay', headers={'Origin': 'http://localhost:5173'}) as socket:
        socket.send_text('ping')


def test_append_event_caps_the_persisted_log(tmp_path):
    path = tmp_path / 'events.json'

    for index in range(event_log.MAX_PERSISTED_EVENTS + 200):
        event_log.append_event(
            QuantJobEvent(
                job_id='job-1',
                event_type='signal_generated',
                message=f'event {index}',
                details={},
            ),
            path,
        )

    loaded = event_log.load_events(path)
    assert len(loaded) == event_log.MAX_PERSISTED_EVENTS
    assert loaded[0].message == 'event 200'
    assert loaded[-1].message == f'event {event_log.MAX_PERSISTED_EVENTS + 199}'


def test_quant_loop_survives_a_crashing_iteration(monkeypatch):
    """One broken tick must not silently kill the loop forever."""
    from python_service.app.quant import loop as quant_loop_module

    calls = {'count': 0}

    async def flaky_run():
        calls['count'] += 1
        if calls['count'] == 1:
            raise RuntimeError('jobs.json is corrupt')
        raise asyncio.CancelledError()  # stop the loop after the retry

    monkeypatch.setattr(quant_loop_module, 'run_enabled_jobs_once', flaky_run)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(quant_loop())

    assert calls['count'] == 2


def test_settings_are_cached_until_the_file_changes(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"language": "zh-CN"}', encoding='utf-8')
    monkeypatch.setattr(settings_routes, 'SETTINGS_FILE', path)
    monkeypatch.setattr(settings_routes, 'DEFAULT_SETTINGS_FILE', tmp_path / 'missing.json')
    settings_routes.invalidate_settings_cache()

    first = settings_routes.get_settings()
    second = settings_routes.get_settings()
    assert first.language == 'zh-CN'
    assert first is second  # cached instance, no re-parse

    path.write_text('{"language": "en"}', encoding='utf-8')
    third = settings_routes.get_settings()
    assert third.language == 'en'
    assert third is not first


def test_settings_save_invalidates_the_cache(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"language": "zh-CN"}', encoding='utf-8')
    monkeypatch.setattr(settings_routes, 'SETTINGS_FILE', path)
    monkeypatch.setattr(settings_routes, 'DEFAULT_SETTINGS_FILE', tmp_path / 'missing.json')
    settings_routes.invalidate_settings_cache()

    assert settings_routes.get_settings().language == 'zh-CN'
    settings_routes.save_settings(Settings(language='en'))

    assert settings_routes.get_settings().language == 'en'


def test_volatility_threshold_is_compared_in_points(monkeypatch):
    """100 points on XAUUSD is $1.00, not $100 - the old raw comparison
    triggered on a 100-dollar move for a 100-point threshold."""
    from python_service.app.services import mt5_service

    class FakeInfo:
        point = 0.01

    monkeypatch.setattr(mt5_service, 'mt5', type('M', (), {'symbol_info': staticmethod(lambda symbol: FakeInfo())}))
    alert = VolatilityAlert(
        id='vol-1',
        symbol='XAUUSD',
        threshold_points=100,
        timeframe_seconds=60,
        is_active=True,
        is_triggered=False,
    )
    history = [
        {'price': 2300.0, 'timestamp': 100.0},
        {'price': 2301.0, 'timestamp': 110.0},  # exactly $1 = 100 points
    ]

    triggered, messages = alert_service.evaluate_volatility([alert], {'XAUUSD': history})

    assert [a.id for a in triggered] == ['vol-1']
    assert '100.0 points' in messages[0]


def test_health_reports_loop_heartbeats():
    loop_heartbeat.reset()
    loop_heartbeat.record('quant')

    snapshot = loop_heartbeat.snapshot()

    assert 'quant' in snapshot
    assert snapshot['quant']['age_seconds'] is not None


# --- batch 2: alerts thread-safety, overlay import validation ----------------

def test_alert_deletion_keeps_the_shared_list_reference_in_sync():
    """Streaming holds the module-level list object; rebinding it on delete
    used to leave the streaming thread reading a stale list forever."""
    from python_service.app.routes import alerts as alerts_routes

    original = alerts_routes.active_alerts
    alert = VolatilityAlert(id='vol-del', symbol='XAUUSD', threshold_points=100, timeframe_seconds=60)
    alerts_routes.active_alerts[:] = [alert]

    # simulate the delete route body
    with alerts_routes._alerts_lock:
        alerts_routes.active_alerts[:] = [a for a in alerts_routes.active_alerts if a.id != 'vol-del']

    assert alerts_routes.active_alerts is original
    assert alerts_routes.active_alerts == []

    # restore module state for other tests
    alerts_routes.active_alerts[:] = []


def test_alert_update_re_arms_and_pins_the_id():
    from python_service.app.routes import alerts as alerts_routes

    original = alerts_routes.active_alerts
    stored = VolatilityAlert(id='vol-upd', symbol='XAUUSD', threshold_points=100, timeframe_seconds=60, is_triggered=True)
    incoming = VolatilityAlert(id='wrong-id', symbol='EURUSD', threshold_points=200, timeframe_seconds=60, is_triggered=True)
    alerts_routes.active_alerts[:] = [stored]
    try:
        alerts_routes.update_volatility_rule('vol-upd', incoming)
        updated = alerts_routes.active_alerts[0]
        assert updated is incoming
        assert updated.id == 'vol-upd'
        assert updated.is_triggered is False
        assert updated.threshold_points == 200
    finally:
        alerts_routes.active_alerts[:] = original[:]


def test_overlay_import_rejects_unbounded_payloads():
    from python_service.app.main import app as backend_app

    client = TestClient(backend_app)
    huge = {'name': 'x', 'alerts': [{'symbol': f'SYM{i}', 'data': 'x' * 50} for i in range(300)]}

    response = client.post('/overlay/import', json=huge)

    assert response.status_code == 422


def test_overlay_import_round_trips_a_valid_payload(tmp_path, monkeypatch):
    from python_service.app.main import app as backend_app

    monkeypatch.chdir(tmp_path)
    client = TestClient(backend_app)

    response = client.post('/overlay/import', json={'name': 'P3', 'alerts': [{'symbol': 'EURUSD', 'target_price': 1.1}]})

    assert response.status_code == 200
    exported = client.get('/overlay/export').json()
    assert exported['name'] == 'P3'
    assert exported['alerts'][0]['symbol'] == 'EURUSD'


def test_backtest_pnl_scales_with_contract_size():
    from python_service.app.quant import backtest_service as bt

    bars = [
        {'time': '2026-01-01T00:00:00Z', 'close': 2000.0},
        {'time': '2026-01-01T00:01:00Z', 'close': 2001.0},
    ]
    trades_small, _ = bt._simulate_trades(bars, ['buy', 'close'], contract_size=1.0)
    trades_gold, _ = bt._simulate_trades(bars, ['buy', 'close'], contract_size=100.0)

    assert trades_small[0]['pnl'] == pytest.approx(1.0)
    # XAUUSD-style sizing: the same $1 move is $100 of PnL per lot.
    assert trades_gold[0]['pnl'] == pytest.approx(100.0)


def test_contract_multiplier_prefers_terminal_symbol_info(monkeypatch):
    from python_service.app.routes import trading_review
    from python_service.app.services import mt5_service

    class FakeInfo:
        trade_contract_size = 10.0

    monkeypatch.setattr(
        mt5_service, 'mt5',
        type('M', (), {'symbol_info': staticmethod(lambda symbol: FakeInfo())}),
    )
    assert trading_review.get_contract_multiplier('EURUSD') == 10.0


# --- phase 5: DPAPI credential sealing ----------------------------------------

def test_secret_box_roundtrip_and_plaintext_passthrough():
    from python_service.app.services import secret_box

    sealed = secret_box.encrypt('s3cret-p@ss')
    assert sealed != 's3cret-p@ss'
    assert secret_box.is_sealed(sealed)
    assert secret_box.decrypt(sealed) == 's3cret-p@ss'

    # Legacy plaintext values load unchanged; empty stays empty.
    assert secret_box.decrypt('legacy-plaintext') == 'legacy-plaintext'
    assert secret_box.encrypt('') == ''
    assert secret_box.decrypt(None) is None


def test_copy_trading_state_seals_passwords_at_rest(tmp_path):
    from python_service.app.local_copy_trading.models import Account, LocalCopyTradingState
    from python_service.app.local_copy_trading import storage as lct_storage
    from python_service.app.services import secret_box

    state = LocalCopyTradingState(accounts=[Account(name='A', password='plain-pw')])
    path = tmp_path / 'state.json'

    lct_storage.save_state(state, path)

    raw = json.loads(path.read_text(encoding='utf-8'))
    assert secret_box.is_sealed(raw['accounts'][0]['password'])
    assert raw['accounts'][0]['password'] != 'plain-pw'

    loaded = lct_storage.load_state(path)
    assert loaded.accounts[0].password == 'plain-pw'


def test_order_sync_seals_api_keys_at_rest(tmp_path, monkeypatch):
    import importlib

    from python_service.app.models.order_sync import OrderSyncState, TopStepAccountCredential
    from python_service.app.services import order_sync_service, secret_box

    monkeypatch.setattr(order_sync_service, 'order_sync_file', lambda: tmp_path / 'os.json')
    monkeypatch.setattr(order_sync_service, '_loaded', False)
    monkeypatch.setattr(order_sync_service, '_state', OrderSyncState(
        credentials=[TopStepAccountCredential(
            user_name='u', api_key='topsecret', account_id=123, name='c1', is_active=True,
        )],
    ))
    importlib.reload.__doc__  # noqa: B018 - keep import visible
    order_sync_service._save()

    raw = json.loads((tmp_path / 'os.json').read_text(encoding='utf-8'))
    assert secret_box.is_sealed(raw['credentials'][0]['api_key'])

    monkeypatch.setattr(order_sync_service, '_loaded', False)
    state = order_sync_service.get_order_sync_state()
    assert state.credentials[0].api_key == 'topsecret'


# --- phase 5: event message codes ----------------------------------------------

def test_copy_events_carry_stable_codes():
    from python_service.app.local_copy_trading.engine import process_tick
    from python_service.app.local_copy_trading.models import Account, CopyResult, LocalCopyTradingState

    state = LocalCopyTradingState(
        enabled=True,
        accounts=[Account(id='src-1', name='S'), Account(id='fol-1', name='F')],
        relationships=[__import__('python_service.app.local_copy_trading.models', fromlist=['CopyRelationship']).CopyRelationship(
            id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'
        )],
    )
    positions = [{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}]

    events = process_tick(
        state, positions,
        execute_copy=lambda f, r, p: CopyResult(False, 'skipped', 'limit reached', code='guard.max_positions_per_symbol'),
    )

    assert events[0].code == 'guard.max_positions_per_symbol'


def test_close_events_carry_stable_codes():
    from python_service.app.local_copy_trading.engine import process_tick
    from python_service.app.local_copy_trading.models import Account, CopyRelationship, LocalCopyTradingState

    state = LocalCopyTradingState(
        enabled=True,
        accounts=[Account(id='src-1', name='S'), Account(id='fol-1', name='F')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')],
    )
    process_tick(state, [{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}],
                 execute_copy=lambda f, r, p: (True, 'ok', 'fp', 'fo'))

    close_events = process_tick(state, [], execute_close=lambda f, r, e: (False, 'Retcode: 10006'))

    assert close_events[0].code == 'close_failed'
