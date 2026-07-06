from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import backtrader as bt
import pandas as pd

from python_service.app.local_copy_trading.runtime import get_state as get_local_copy_trading_state
from python_service.app.quant import event_log as quant_event_log
from python_service.app.quant.market_data import DEFAULT_MARKET_DATA_PATH, ensure_recent_bars
from python_service.app.quant.mt5_execution import execute_signal
from python_service.app.quant import storage as quant_storage
from python_service.app.quant.models import QuantJob, QuantJobEvent, QuantJobEventType, SignalAction, utc_now_iso
from python_service.app.quant.strategy_registry import get_strategy_module, list_strategies


def load_all_jobs() -> list[QuantJob]:
    return quant_storage.load_jobs(quant_storage.DEFAULT_JOBS_PATH)


def save_all_jobs(jobs: list[QuantJob]) -> None:
    quant_storage.save_jobs(jobs, quant_storage.DEFAULT_JOBS_PATH)


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _list_runtime_accounts() -> list[dict]:
    state = get_local_copy_trading_state()
    accounts: list[dict] = []
    seen_ids: set[str] = set()

    for account in state.accounts:
        if not account.is_active or not account.id or account.id in seen_ids:
            continue
        seen_ids.add(account.id)
        accounts.append({
            'id': account.id,
            'name': account.name,
            'login': account.login,
            'server': account.server,
            'terminal_path': account.terminal_path,
            'password': account.password,
            'connection_type': account.connection_type,
        })

    return accounts


def list_available_accounts() -> list[dict]:
    return [
        {
            'id': account['id'],
            'name': account['name'],
            'login': account['login'],
            'server': account['server'],
            'terminal_path': account['terminal_path'],
            'connection_type': account['connection_type'],
        }
        for account in _list_runtime_accounts()
    ]


def get_account_by_id(account_id: str) -> dict:
    for account in _list_runtime_accounts():
        if account['id'] == account_id:
            return account
    raise LookupError(f'Unknown quant account: {account_id}')


def list_available_strategies() -> list[dict]:
    return [
        {
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'timeframes': item.timeframes,
            'module_path': item.module_path,
        }
        for item in list_strategies()
    ]


def ensure_strategy_exists(strategy_id: str) -> None:
    if any(item['id'] == strategy_id for item in list_available_strategies()):
        return
    raise ValueError(f'Unknown quant strategy: {strategy_id}')


def build_overview() -> dict:
    return {
        'accounts': list_available_accounts(),
        'strategies': list_available_strategies(),
        'jobs': [job.model_dump() for job in load_all_jobs()],
    }


def get_job(job_id: str) -> QuantJob:
    for job in load_all_jobs():
        if job.id == job_id:
            return job
    raise LookupError(f'Unknown quant job: {job_id}')


def record_job_event(job: QuantJob, event_type: QuantJobEventType, message: str, details: dict[str, object] | None = None) -> QuantJobEvent:
    return quant_event_log.append_event(QuantJobEvent(
        job_id=job.id,
        event_type=event_type,
        message=message,
        details=details or {},
    ))


def validate_unique_account_symbol(
    jobs: list[QuantJob],
    account_id: str,
    symbol: str,
    *,
    ignore_job_id: str | None = None,
) -> None:
    normalized_symbol = normalize_symbol(symbol)
    for job in jobs:
        if ignore_job_id and job.id == ignore_job_id:
            continue
        if job.enabled and job.account_id == account_id and normalize_symbol(job.symbol) == normalized_symbol:
            raise ValueError('Only one enabled quant job per account and symbol is allowed in V1')


def add_job(payload: Mapping[str, object]) -> QuantJob:
    jobs = load_all_jobs()
    new_job = QuantJob(**payload)
    jobs.append(new_job)
    save_all_jobs(jobs)
    return new_job


def replace_job(job_id: str, payload: Mapping[str, object]) -> QuantJob:
    jobs = load_all_jobs()
    updated_jobs: list[QuantJob] = []
    updated_job: QuantJob | None = None

    for job in jobs:
        if job.id != job_id:
            updated_jobs.append(job)
            continue

        updates = dict(payload)
        if 'enabled' in updates:
            updates['status'] = 'running' if updates['enabled'] else 'stopped'
            if updates['enabled']:
                updates['last_error'] = None
        updates['updated_at'] = utc_now_iso()
        updated_job = job.model_copy(update=updates)
        updated_jobs.append(updated_job)

    if updated_job is None:
        raise LookupError(f'Unknown quant job: {job_id}')

    save_all_jobs(updated_jobs)
    return updated_job


def remove_job(job_id: str) -> QuantJob:
    jobs = load_all_jobs()
    remaining_jobs: list[QuantJob] = []
    deleted_job: QuantJob | None = None

    for job in jobs:
        if job.id == job_id:
            deleted_job = job
            continue
        remaining_jobs.append(job)

    if deleted_job is None:
        raise LookupError(f'Unknown quant job: {job_id}')

    save_all_jobs(remaining_jobs)
    return deleted_job


def set_job_enabled(job_id: str, enabled: bool) -> QuantJob:
    return replace_job(job_id, {'enabled': enabled})


def resolve_signal_action(job: QuantJob, signal: SignalAction, bar_time: str | None) -> SignalAction:
    if bar_time and job.last_bar_time == bar_time:
        return 'hold'
    return signal


def get_account_for_job(job: QuantJob) -> dict:
    return get_account_by_id(job.account_id)


def evaluate_strategy_signal(strategy_id: str, bars: list[dict]) -> tuple[SignalAction, str | None]:
    if len(bars) < 30:
        return 'hold', bars[-1]['time'] if bars else None

    strategy_module = get_strategy_module(strategy_id)
    frame = pd.DataFrame(bars)
    frame['datetime'] = pd.to_datetime(frame['time'], utc=True)
    frame = frame.set_index('datetime').rename(columns={'tick_volume': 'volume'})

    data = bt.feeds.PandasData(dataname=frame[['open', 'high', 'low', 'close', 'volume']])
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(strategy_module.Strategy)
    cerebro.adddata(data)
    strategies = cerebro.run()

    latest_bar_time = bars[-1]['time']
    signal = getattr(strategies[0], 'signal_output', 'hold') if strategies else 'hold'
    if signal not in {'buy', 'sell', 'close', 'hold'}:
        signal = 'hold'
    return signal, latest_bar_time


def run_job_once(job: QuantJob, *, db_path: Path | str = DEFAULT_MARKET_DATA_PATH) -> QuantJob:
    account = get_account_for_job(job)
    bars = ensure_recent_bars(
        db_path=db_path,
        account=account,
        account_id=job.account_id,
        symbol=job.symbol,
        timeframe=job.timeframe,
        min_bars=100,
    )
    signal, bar_time = evaluate_strategy_signal(job.strategy_id, bars)
    action = resolve_signal_action(job, signal=signal, bar_time=bar_time)
    record_job_event(job, 'signal_generated', f'{signal} signal evaluated for {job.symbol}', {
        'signal': signal,
        'action': action,
        'bar_time': bar_time,
        'execution_mode': job.execution_mode,
    })

    if job.execution_mode == 'live' and action != 'hold':
        execute_signal(account=account, symbol=job.symbol, lot=job.lot, signal=action)
        record_job_event(job, 'order_sent', f'{action} order sent for {job.symbol}', {
            'signal': signal,
            'action': action,
            'bar_time': bar_time,
            'lot': job.lot,
        })
    elif job.execution_mode == 'paper' and action != 'hold':
        record_job_event(job, 'order_skipped_paper', f'{action} signal kept in paper mode for {job.symbol}', {
            'signal': signal,
            'action': action,
            'bar_time': bar_time,
            'lot': job.lot,
        })

    return job.model_copy(update={
        'status': 'running',
        'last_signal': signal,
        'last_bar_time': bar_time,
        'last_error': None,
        'updated_at': utc_now_iso(),
    })


async def run_enabled_jobs_once(*, db_path: Path | str = DEFAULT_MARKET_DATA_PATH) -> None:
    jobs = load_all_jobs()
    updated_jobs: list[QuantJob] = []

    for job in jobs:
        if not job.enabled:
            updated_jobs.append(job)
            continue

        try:
            updated_jobs.append(run_job_once(job, db_path=db_path))
        except Exception as error:
            record_job_event(job, 'strategy_error', str(error), {
                'execution_mode': job.execution_mode,
            })
            updated_jobs.append(job.model_copy(update={
                'status': 'error',
                'last_error': str(error),
                'updated_at': utc_now_iso(),
            }))

    save_all_jobs(updated_jobs)
