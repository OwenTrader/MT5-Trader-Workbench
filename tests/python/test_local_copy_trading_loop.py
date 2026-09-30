from python_service.app.local_copy_trading import loop
from python_service.app.local_copy_trading.models import (
    Account,
    CopyRelationship,
    CopyTradingRiskSettings,
    CopyResult,
    LocalCopyTradingState,
    SyncEvent,
)
from python_service.app.local_copy_trading.runtime import add_event


def _event(status, position_id, relationship_id='rel-1', created_at='2026-09-30T10:00:00+00:00'):
    return SyncEvent(
        relationship_id=relationship_id,
        source_account_id='src-1',
        follower_account_id='fol-1',
        position_id=position_id,
        symbol='XAUUSD',
        status=status,
        message='',
        created_at=created_at,
    )


def _state(**overrides):
    fields = {
        'enabled': True,
        'accounts': [Account(id='src-1', name='Main'), Account(id='fol-1', name='Follower')],
        'relationships': [
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')
        ],
    }
    fields.update(overrides)
    return LocalCopyTradingState(**fields)


def test_daily_open_count_counts_positions_first_copied_today():
    from datetime import datetime, timezone

    state = _state()
    today = datetime.now(timezone.utc).date().isoformat()
    add_event(state, _event('copied', 'pos-1', created_at=f'{today}T09:00:00+00:00'))
    add_event(state, _event('copied', 'pos-1', created_at=f'{today}T09:05:00+00:00'))  # re-sync, not a new open
    add_event(state, _event('copied', 'pos-2', created_at=f'{today}T10:00:00+00:00'))
    add_event(state, _event('copied', 'pos-3', created_at='2026-01-01T10:00:00+00:00'))  # yesterday

    assert loop._daily_open_count(state, 'rel-1', today) == 2


def test_consecutive_failures_skips_close_and_drift_failures():
    state = _state()
    add_event(state, _event('copied', 'pos-0'))
    add_event(state, _event('failed', 'pos-gone'))  # close/drift failure: source already gone
    add_event(state, _event('failed', 'pos-1'))
    add_event(state, _event('failed', 'pos-1'))

    assert loop._consecutive_failures(state, 'rel-1', {'pos-1'}) == 2
    assert loop._consecutive_failures(state, 'rel-1', set()) == 0


def test_run_tick_retries_failed_work_despite_an_unchanged_signature(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    state = _state()
    add_event(state, _event('copied', 'pos-1'))
    source_positions = []  # the source position is gone: a close is still owing

    monkeypatch.setattr(loop, 'get_source_positions', lambda state: source_positions)
    monkeypatch.setattr(loop.copy_trading_db, 'get_recorded_volume', lambda relationship_id, position_id: None)
    monkeypatch.setattr(loop.reconcile, 'reconcile', lambda *args, **kwargs: [])

    ticks = []

    def spy_process_tick(*args, **kwargs):
        ticks.append(1)

    monkeypatch.setattr(loop, 'process_tick', spy_process_tick)

    signature = loop._run_tick(state, None)
    loop._run_tick(state, signature)  # unchanged snapshot: must still retry the owing close

    assert len(ticks) == 2


def test_run_tick_skips_when_idle_and_the_signature_is_unchanged(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    state = _state()

    monkeypatch.setattr(loop, 'get_source_positions', lambda state: [])
    monkeypatch.setattr(loop.reconcile, 'reconcile', lambda *args, **kwargs: [])

    ticks = []

    def spy_process_tick(*args, **kwargs):
        ticks.append(1)

    monkeypatch.setattr(loop, 'process_tick', spy_process_tick)

    signature = loop._run_tick(state, None)
    loop._run_tick(state, signature)

    assert len(ticks) == 1


def test_run_tick_passes_risk_settings_and_counters_to_execute_copy(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    state = _state()
    source_positions = [{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD', 'volume': 0.1}]

    settings = CopyTradingRiskSettings(max_consecutive_failures=7)
    monkeypatch.setattr(loop, 'get_source_positions', lambda state: source_positions)
    monkeypatch.setattr(loop.guards, 'load_risk_settings', lambda: settings)
    monkeypatch.setattr(loop.reconcile, 'reconcile', lambda *args, **kwargs: [])
    monkeypatch.setattr(loop.copy_trading_db, 'get_recorded_volume', lambda relationship_id, position_id: None)

    captured = {}

    def fake_execute_copy(follower, relationship, position, **kwargs):
        captured.update(kwargs)
        return CopyResult(True, 'copied', 'ok')

    monkeypatch.setattr(loop.copy_service, 'execute_copy', fake_execute_copy)

    loop._run_tick(state, None)

    assert captured['risk_settings'].max_consecutive_failures == 7
    assert captured['daily_open_count'] == 0
    assert captured['consecutive_failures'] == 0
