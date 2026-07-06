from python_service.app.quant.event_log import append_event, list_events
from python_service.app.quant import event_log as quant_event_log
from python_service.app.quant.models import QuantJobEvent


def test_event_log_appends_and_lists_events_by_job(tmp_path):
    events_path = tmp_path / 'events.json'
    append_event(QuantJobEvent(job_id='job-1', event_type='signal_generated', message='first signal', created_at='2026-06-10T00:00:00+00:00'), events_path)
    append_event(QuantJobEvent(job_id='job-2', event_type='strategy_error', message='ignore me', created_at='2026-06-10T00:01:00+00:00'), events_path)
    append_event(QuantJobEvent(job_id='job-1', event_type='order_sent', message='second signal', created_at='2026-06-10T00:02:00+00:00'), events_path)

    events = list_events('job-1', events_path)

    assert [event.message for event in events] == ['second signal', 'first signal']


def test_event_log_uses_overridden_default_path_when_storage_path_is_omitted(tmp_path, monkeypatch):
    monkeypatch.setattr(quant_event_log, 'DEFAULT_EVENTS_PATH', tmp_path / 'events.json')

    append_event(QuantJobEvent(job_id='job-1', event_type='signal_generated', message='default path signal'))

    events = list_events('job-1')

    assert [event.message for event in events] == ['default path signal']
