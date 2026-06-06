from python_service.app.quant.models import QuantJob
from python_service.app.quant.storage import load_jobs, save_jobs


def test_load_jobs_returns_empty_list_when_file_missing(tmp_path):
    assert load_jobs(tmp_path / 'jobs.json') == []


def test_save_jobs_round_trips_json(tmp_path):
    storage_path = tmp_path / 'jobs.json'
    jobs = [
        QuantJob(
            id='job-1',
            name='Gold M5 Trend',
            account_id='acc-1',
            strategy_id='sma_cross',
            symbol='XAUUSD',
            timeframe='M5',
            lot=0.01,
        )
    ]

    save_jobs(jobs, storage_path)
    loaded = load_jobs(storage_path)

    assert [job.id for job in loaded] == ['job-1']
    assert loaded[0].symbol == 'XAUUSD'
