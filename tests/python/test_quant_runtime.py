import asyncio
from datetime import datetime, timedelta, timezone
import pytest

from python_service.app.local_copy_trading.models import LocalCopyTradingState, SourceAccount
from python_service.app.local_copy_trading.runtime import reset_state
from python_service.app.quant import storage as quant_storage
from python_service.app.quant.market_data import ensure_recent_bars
from python_service.app.quant.models import QuantJob
from python_service.app.quant.runtime import (
    get_account_by_id,
    list_available_accounts,
    resolve_signal_action,
    run_enabled_jobs_once,
    run_job_once,
    set_job_enabled,
    validate_unique_account_symbol,
)


def test_resolve_signal_action_ignores_duplicate_bar_signal():
    job = QuantJob(
        id='job-1',
        name='Gold M5 Trend',
        account_id='acc-1',
        strategy_id='sma_cross',
        symbol='XAUUSD',
        timeframe='M5',
        lot=0.01,
        enabled=True,
        status='running',
        last_bar_time='2026-06-05T08:35:00+00:00',
        last_signal='buy',
    )

    action = resolve_signal_action(job, signal='buy', bar_time='2026-06-05T08:35:00+00:00')

    assert action == 'hold'


def test_resolve_signal_action_ignores_changed_signal_on_same_bar():
    job = QuantJob(
        id='job-1',
        name='Gold M5 Trend',
        account_id='acc-1',
        strategy_id='sma_cross',
        symbol='XAUUSD',
        timeframe='M5',
        lot=0.01,
        enabled=True,
        status='running',
        last_bar_time='2026-06-05T08:35:00+00:00',
        last_signal='buy',
    )

    action = resolve_signal_action(job, signal='close', bar_time='2026-06-05T08:35:00+00:00')

    assert action == 'hold'


def test_validate_unique_account_symbol_rejects_existing_enabled_job():
    jobs = [
        QuantJob(
            id='job-1',
            name='Gold M5 Trend',
            account_id='acc-1',
            strategy_id='sma_cross',
            symbol='XAUUSD',
            timeframe='M5',
            lot=0.01,
            enabled=True,
            status='running',
        )
    ]

    with pytest.raises(ValueError, match='Only one enabled quant job per account and symbol is allowed in V1'):
        validate_unique_account_symbol(jobs, 'acc-1', 'xauusd')


def test_runtime_account_lookup_keeps_password_internal_only():
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

    public_account = list_available_accounts()[0]
    runtime_account = get_account_by_id('acc-1')

    assert 'password' not in public_account
    assert runtime_account['password'] == 'secret'


def test_set_job_enabled_persists_runtime_status(tmp_path, monkeypatch):
    jobs_path = tmp_path / 'jobs.json'
    monkeypatch.setattr(quant_storage, 'DEFAULT_JOBS_PATH', jobs_path)
    quant_storage.save_jobs(
        [
            QuantJob(
                id='job-1',
                name='Gold M5 Trend',
                account_id='acc-1',
                strategy_id='sma_cross',
                symbol='XAUUSD',
                timeframe='M5',
                lot=0.01,
            )
        ],
        jobs_path,
    )

    updated = set_job_enabled('job-1', True)
    loaded = quant_storage.load_jobs(jobs_path)

    assert updated.enabled is True
    assert updated.status == 'running'
    assert loaded[0].enabled is True
    assert loaded[0].status == 'running'


def test_ensure_recent_bars_refreshes_only_latest_when_cache_is_stale(monkeypatch):
    fetched = {}
    stale_time = (datetime.now(timezone.utc) - timedelta(minutes=17)).isoformat()

    monkeypatch.setattr(
        'python_service.app.quant.market_data.load_recent_bars',
        lambda *args, **kwargs: [
            {
                'time': '2026-06-05T08:30:00+00:00',
                'open': 1.0,
                'high': 2.0,
                'low': 0.5,
                'close': 1.0,
                'tick_volume': 10,
            },
            {
                'time': stale_time,
                'open': 1.0,
                'high': 2.1,
                'low': 0.9,
                'close': 2.0,
                'tick_volume': 12,
            },
        ],
    )
    monkeypatch.setattr(
        'python_service.app.quant.market_data.backfill_from_mt5',
        lambda **kwargs: fetched.setdefault('bars', kwargs['bars']),
    )

    rows = ensure_recent_bars(
        db_path='ignored.sqlite3',
        account={'terminal_path': 'C:/MT5/terminal64.exe', 'login': '1001', 'password': 'secret', 'server': 'demo'},
        account_id='acc-1',
        symbol='XAUUSD',
        timeframe='M5',
        min_bars=2,
    )

    assert fetched['bars'] >= 4
    assert rows[-1]['time'] == stale_time


def test_run_job_once_backfills_executes_and_records_signal(monkeypatch):
    job = QuantJob(
        id='job-1',
        name='Gold M5 Trend',
        account_id='acc-1',
        strategy_id='sma_cross',
        symbol='XAUUSD',
        timeframe='M5',
        lot=0.01,
        enabled=True,
        status='running',
    )

    monkeypatch.setattr('python_service.app.quant.runtime.get_account_for_job', lambda job: {
        'id': 'acc-1',
        'terminal_path': 'C:/MT5/terminal64.exe',
        'login': '1001',
        'password': 'secret',
        'server': 'demo',
    })
    monkeypatch.setattr('python_service.app.quant.runtime.ensure_recent_bars', lambda **kwargs: [
        {'time': '2026-06-05T08:30:00+00:00', 'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.0, 'tick_volume': 10},
        {'time': '2026-06-05T08:35:00+00:00', 'open': 1.0, 'high': 2.1, 'low': 0.9, 'close': 2.0, 'tick_volume': 12},
    ])
    monkeypatch.setattr('python_service.app.quant.runtime.evaluate_strategy_signal', lambda *args, **kwargs: ('buy', '2026-06-05T08:35:00+00:00'))
    executed = {}
    monkeypatch.setattr('python_service.app.quant.runtime.execute_signal', lambda **kwargs: executed.setdefault('signal', kwargs['signal']))

    updated = run_job_once(job)

    assert updated.last_signal == 'buy'
    assert updated.last_bar_time == '2026-06-05T08:35:00+00:00'
    assert updated.status == 'running'
    assert executed['signal'] == 'buy'


def test_run_enabled_jobs_once_marks_job_error_and_persists_jobs(tmp_path, monkeypatch):
    jobs_path = tmp_path / 'jobs.json'
    monkeypatch.setattr(quant_storage, 'DEFAULT_JOBS_PATH', jobs_path)
    quant_storage.save_jobs(
        [
            QuantJob(
                id='job-1',
                name='Gold M5 Trend',
                account_id='acc-1',
                strategy_id='sma_cross',
                symbol='XAUUSD',
                timeframe='M5',
                lot=0.01,
                enabled=True,
                status='running',
            ),
            QuantJob(
                id='job-2',
                name='Gold M15 Trend',
                account_id='acc-2',
                strategy_id='sma_cross',
                symbol='EURUSD',
                timeframe='M15',
                lot=0.02,
                enabled=False,
                status='stopped',
            ),
        ],
        jobs_path,
    )
    monkeypatch.setattr(
        'python_service.app.quant.runtime.run_job_once',
        lambda job, **kwargs: (_ for _ in ()).throw(RuntimeError('execution failed')) if job.id == 'job-1' else job,
    )

    asyncio.run(run_enabled_jobs_once())
    loaded = quant_storage.load_jobs(jobs_path)

    assert loaded[0].status == 'error'
    assert loaded[0].last_error == 'execution failed'
    assert loaded[1].status == 'stopped'
