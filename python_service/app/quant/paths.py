import os
from pathlib import Path


DEFAULT_QUANT_ROOT_DIR = Path('storage/python_quant')


def get_quant_root_dir() -> Path:
    configured = os.environ.get('PYTHON_QUANT_DATA_DIR', '').strip()
    if configured:
        return Path(configured)
    return DEFAULT_QUANT_ROOT_DIR


def get_user_strategies_dir() -> Path:
    configured = os.environ.get('PYTHON_QUANT_STRATEGIES_DIR', '').strip()
    if configured:
        return Path(configured)
    return get_quant_root_dir() / 'strategies'


def get_jobs_path() -> Path:
    configured = os.environ.get('PYTHON_QUANT_JOBS_PATH', '').strip()
    if configured:
        return Path(configured)
    return get_quant_root_dir() / 'jobs.json'


def get_events_path() -> Path:
    configured = os.environ.get('PYTHON_QUANT_EVENTS_PATH', '').strip()
    if configured:
        return Path(configured)
    return get_quant_root_dir() / 'events.json'


def get_market_data_path() -> Path:
    configured = os.environ.get('PYTHON_QUANT_MARKET_DATA_PATH', '').strip()
    if configured:
        return Path(configured)
    return get_quant_root_dir() / 'market_data.sqlite3'
