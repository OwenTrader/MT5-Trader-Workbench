"""Single source of truth for backend storage locations.

Electron injects APP_STORAGE_DIR (the user-writable userData/storage dir)
for packaged builds; without it we fall back to CWD-relative storage/ which
matches dev (repo root) and pytest (tmp cwd) behavior. Resolved per call,
never at import, so chdir-based tests stay isolated.

Writing into a Program Files install directory was the failure this module
exists to prevent: every runtime file must live under APP_STORAGE_DIR.
"""

from __future__ import annotations

import os
from pathlib import Path


def storage_dir() -> Path:
    return Path(os.environ.get('APP_STORAGE_DIR', 'storage'))


def storage_file(name: str) -> Path:
    return storage_dir() / name


def alerts_file() -> Path:
    return storage_file('alerts.json')


def order_sync_file() -> Path:
    return storage_file('order_sync.json')


def risk_control_file() -> Path:
    return storage_file('risk-control.json')


def overlay_config_file() -> Path:
    return storage_file('overlay_config.json')


def kline_db_path() -> Path:
    return storage_file('kline_data.db')


def copy_trading_db_path() -> Path:
    return storage_file('local_copy_trading.db')


def copy_trading_state_file() -> Path:
    return storage_file('local_copy_trading.json')


def copy_trading_risk_file() -> Path:
    return storage_file('copy-trading-risk.json')
