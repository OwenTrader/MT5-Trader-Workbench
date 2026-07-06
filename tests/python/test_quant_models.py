from python_service.app.quant.models import QuantJob, QuantJobEvent
from python_service.app.quant.strategy_registry import list_strategies


def test_quant_job_defaults_to_stopped_state():
    job = QuantJob(
        name='Gold M5 Trend',
        account_id='acc-1',
        strategy_id='sma_cross',
        symbol='XAUUSD',
        timeframe='M5',
        lot=0.01,
    )

    assert job.enabled is False
    assert job.execution_mode == 'paper'
    assert job.status == 'stopped'
    assert job.last_signal is None


def test_list_strategies_includes_builtin_sma_cross():
    strategies = list_strategies()

    assert any(item.id == 'sma_cross' for item in strategies)


def test_quant_job_event_defaults_timestamp_and_details():
    event = QuantJobEvent(
        job_id='job-1',
        event_type='signal_generated',
        message='buy signal evaluated',
    )

    assert event.details == {}
    assert event.created_at
