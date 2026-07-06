from fastapi import FastAPI
from fastapi.testclient import TestClient

from python_service.app.local_copy_trading.models import LocalCopyTradingState, SourceAccount
from python_service.app.local_copy_trading.runtime import reset_state
from python_service.app.quant import event_log as quant_event_log
from python_service.app.quant import storage as quant_storage
from python_service.app.quant.models import QuantJobEvent
from python_service.app.quant.routes import router as quant_router


def build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(quant_router)
    return app


def seed_accounts() -> None:
    reset_state(
        LocalCopyTradingState(
            source_accounts=[
                SourceAccount(
                    id='acc-1',
                    name='Main A',
                    connection_type='mt5_terminal',
                    terminal_path='C:/MT5/terminal64.exe',
                    login='1001',
                    server='demo',
                    password='secret',
                    is_active=True,
                )
            ]
        )
    )


def prepare_client(tmp_path, monkeypatch) -> TestClient:
    seed_accounts()
    monkeypatch.setattr(quant_storage, 'DEFAULT_JOBS_PATH', tmp_path / 'jobs.json')
    monkeypatch.setattr(quant_event_log, 'DEFAULT_EVENTS_PATH', tmp_path / 'events.json')
    return TestClient(build_test_app())


def test_python_quant_overview_returns_accounts_strategies_and_jobs(tmp_path, monkeypatch):
    client = prepare_client(tmp_path, monkeypatch)

    response = client.get('/python-quant/overview')

    assert response.status_code == 200
    payload = response.json()
    assert 'accounts' in payload
    assert 'strategies' in payload
    assert 'jobs' in payload
    assert payload['accounts'][0]['id'] == 'acc-1'


def test_create_job_route_persists_payload(tmp_path, monkeypatch):
    client = prepare_client(tmp_path, monkeypatch)

    response = client.post('/python-quant/jobs', json={
        'name': 'Gold M5 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'xauusd',
        'timeframe': 'M5',
        'lot': 0.01,
        'execution_mode': 'live',
    })

    assert response.status_code == 200
    assert response.json()['symbol'] == 'XAUUSD'
    assert response.json()['execution_mode'] == 'live'
    loaded = quant_storage.load_jobs(tmp_path / 'jobs.json')
    assert loaded[0].id == response.json()['id']
    assert loaded[0].execution_mode == 'live'


def test_update_job_route_persists_mutations(tmp_path, monkeypatch):
    client = prepare_client(tmp_path, monkeypatch)
    created = client.post('/python-quant/jobs', json={
        'name': 'Gold M5 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M5',
        'lot': 0.01,
    }).json()

    response = client.put(f"/python-quant/jobs/{created['id']}", json={
        'name': 'Gold M15 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M15',
        'lot': 0.02,
        'execution_mode': 'live',
    })

    assert response.status_code == 200
    assert response.json()['timeframe'] == 'M15'
    assert response.json()['lot'] == 0.02
    assert response.json()['execution_mode'] == 'live'


def test_update_job_route_preserves_execution_mode_when_field_is_omitted(tmp_path, monkeypatch):
    client = prepare_client(tmp_path, monkeypatch)
    created = client.post('/python-quant/jobs', json={
        'name': 'Gold M5 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M5',
        'lot': 0.01,
        'execution_mode': 'live',
    }).json()

    response = client.put(f"/python-quant/jobs/{created['id']}", json={
        'name': 'Gold M15 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M15',
        'lot': 0.02,
    })

    assert response.status_code == 200
    assert response.json()['execution_mode'] == 'live'


def test_delete_job_route_removes_job(tmp_path, monkeypatch):
    client = prepare_client(tmp_path, monkeypatch)
    created = client.post('/python-quant/jobs', json={
        'name': 'Gold M5 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M5',
        'lot': 0.01,
    }).json()

    response = client.delete(f"/python-quant/jobs/{created['id']}")

    assert response.status_code == 200
    assert response.json()['id'] == created['id']
    assert quant_storage.load_jobs(tmp_path / 'jobs.json') == []


def test_start_and_stop_job_routes_toggle_runtime_state(tmp_path, monkeypatch):
    client = prepare_client(tmp_path, monkeypatch)
    created = client.post('/python-quant/jobs', json={
        'name': 'Gold M5 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M5',
        'lot': 0.01,
    }).json()

    started = client.post(f"/python-quant/jobs/{created['id']}/start")
    stopped = client.post(f"/python-quant/jobs/{created['id']}/stop")

    assert started.status_code == 200
    assert started.json()['enabled'] is True
    assert started.json()['status'] == 'running'
    assert stopped.status_code == 200
    assert stopped.json()['enabled'] is False
    assert stopped.json()['status'] == 'stopped'


def test_start_job_route_rejects_duplicate_enabled_account_symbol(tmp_path, monkeypatch):
    client = prepare_client(tmp_path, monkeypatch)
    first = client.post('/python-quant/jobs', json={
        'name': 'Gold M5 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M5',
        'lot': 0.01,
    }).json()
    second = client.post('/python-quant/jobs', json={
        'name': 'Gold M15 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M15',
        'lot': 0.02,
    }).json()

    client.post(f"/python-quant/jobs/{first['id']}/start")
    response = client.post(f"/python-quant/jobs/{second['id']}/start")

    assert response.status_code == 400
    assert response.json()['detail'] == 'Only one enabled quant job per account and symbol is allowed in V1'


def test_backfill_route_returns_inserted_row_count(tmp_path, monkeypatch):
    client = prepare_client(tmp_path, monkeypatch)
    monkeypatch.setattr('python_service.app.quant.routes.request_backfill', lambda **kwargs: 120)

    response = client.post('/python-quant/data/backfill', json={
        'account_id': 'acc-1',
        'symbol': 'XAUUSD',
        'timeframe': 'M5',
        'bars': 120,
    })

    assert response.status_code == 200
    assert response.json() == {'inserted_rows': 120}


def test_job_events_route_returns_recent_job_events(tmp_path, monkeypatch):
    client = prepare_client(tmp_path, monkeypatch)
    created = client.post('/python-quant/jobs', json={
        'name': 'Gold M5 Trend',
        'account_id': 'acc-1',
        'strategy_id': 'sma_cross',
        'symbol': 'XAUUSD',
        'timeframe': 'M5',
        'lot': 0.01,
    }).json()
    quant_event_log.append_event(QuantJobEvent(job_id=created['id'], event_type='signal_generated', message='buy signal evaluated'))

    response = client.get(f"/python-quant/jobs/{created['id']}/events")

    assert response.status_code == 200
    assert response.json()[0]['message'] == 'buy signal evaluated'
