"""Phase 3 robustness behaviors: WS origin guard, event-log cap, quant loop
resilience, settings cache, volatility point units, loop heartbeats."""

import asyncio

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
