from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import backtrader as bt
import pandas as pd

from python_service.app.quant.backtest_models import (
    BacktestEquityPoint,
    BacktestRange,
    BacktestResult,
    BacktestStrategyRef,
    BacktestSummary,
    BacktestTrade,
)
from python_service.app.quant.market_data import DEFAULT_MARKET_DATA_PATH, load_bars_for_range
from python_service.app.quant.models import Timeframe
from python_service.app.quant.strategy_registry import get_strategy_module, list_strategies


INITIAL_EQUITY = 10_000.0


@dataclass
class _OpenPosition:
    side: str
    entry_time: str
    entry_price: float


def run_backtest(
    *,
    account_id: str,
    strategy_id: str,
    symbol: str,
    timeframe: Timeframe,
    start_at: str,
    end_at: str,
    db_path: Path | str = DEFAULT_MARKET_DATA_PATH,
) -> dict:
    bars = load_bars_for_range(
        db_path=db_path,
        account_id=account_id,
        symbol=symbol,
        timeframe=timeframe,
        start_at=start_at,
        end_at=end_at,
    )
    if not bars:
        raise ValueError('No cached bars available for the requested range')

    descriptor = _get_strategy_descriptor(strategy_id)
    signals = _evaluate_strategy_signals(strategy_id, bars)
    trades, equity_curve = _simulate_trades(bars, signals)
    summary = _build_summary(equity_curve, trades)

    result = BacktestResult(
        strategy=BacktestStrategyRef(id=descriptor.id, name=descriptor.name),
        symbol=symbol,
        timeframe=timeframe,
        range=BacktestRange(start_at=start_at, end_at=end_at),
        summary=summary,
        equity_curve=[BacktestEquityPoint(**point) for point in equity_curve],
        trades=[BacktestTrade(**trade) for trade in trades],
    )
    return result.model_dump()


def _get_strategy_descriptor(strategy_id: str):
    for descriptor in list_strategies():
        if descriptor.id == strategy_id:
            return descriptor
    raise ValueError(f'Unknown strategy: {strategy_id}')


def _evaluate_strategy_signals(strategy_id: str, bars: list[dict]) -> list[str]:
    strategy_module = get_strategy_module(strategy_id)
    frame = pd.DataFrame(bars)
    frame['datetime'] = pd.to_datetime(frame['time'], utc=True)
    frame = frame.set_index('datetime').rename(columns={'tick_volume': 'volume'})

    data = bt.feeds.PandasData(dataname=frame[['open', 'high', 'low', 'close', 'volume']])
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.addstrategy(_wrap_strategy_for_signal_history(strategy_module.Strategy))
    cerebro.adddata(data)
    strategies = cerebro.run()
    if not strategies:
        return []
    return list(getattr(strategies[0], 'signal_history', []))


def _wrap_strategy_for_signal_history(strategy_class: type[bt.Strategy]) -> type[bt.Strategy]:
    class WrappedStrategy(strategy_class):
        def __init__(self):
            super().__init__()
            self.signal_history: list[str] = []

        def next(self):
            super().next()
            signal = getattr(self, 'signal_output', 'hold')
            if signal not in {'buy', 'sell', 'close', 'hold'}:
                signal = 'hold'
            self.signal_history.append(signal)

    return WrappedStrategy


def _simulate_trades(bars: list[dict], signals: list[str]) -> tuple[list[dict], list[dict]]:
    cash = INITIAL_EQUITY
    position: _OpenPosition | None = None
    trades: list[dict] = []
    equity_curve: list[dict] = []

    for index, bar in enumerate(bars):
        signal = signals[index] if index < len(signals) else 'hold'
        close_price = float(bar['close'])

        if signal == 'buy':
            cash, position = _reverse_or_open_position(cash, position, trades, bar['time'], close_price, 'buy')
        elif signal == 'sell':
            cash, position = _reverse_or_open_position(cash, position, trades, bar['time'], close_price, 'sell')
        elif signal == 'close' and position is not None:
            cash = _close_position(cash, position, trades, bar['time'], close_price)
            position = None

        equity_curve.append({
            'time': bar['time'],
            'equity': round(_equity_value(cash, position, close_price), 4),
        })

    return trades, equity_curve


def _reverse_or_open_position(
    cash: float,
    position: _OpenPosition | None,
    trades: list[dict],
    exit_or_entry_time: str,
    price: float,
    next_side: str,
) -> tuple[float, _OpenPosition]:
    if position is not None and position.side != next_side:
        cash = _close_position(cash, position, trades, exit_or_entry_time, price)
        position = None

    if position is None:
        position = _OpenPosition(side=next_side, entry_time=exit_or_entry_time, entry_price=price)

    return cash, position


def _close_position(cash: float, position: _OpenPosition, trades: list[dict], exit_time: str, exit_price: float) -> float:
    pnl = _calculate_pnl(position.side, position.entry_price, exit_price)
    trades.append({
        'entry_time': position.entry_time,
        'exit_time': exit_time,
        'side': position.side,
        'pnl': round(pnl, 4),
    })
    return cash + pnl


def _equity_value(cash: float, position: _OpenPosition | None, current_price: float) -> float:
    if position is None:
        return cash
    return cash + _calculate_pnl(position.side, position.entry_price, current_price)


def _calculate_pnl(side: str, entry_price: float, exit_price: float) -> float:
    if side == 'sell':
        return entry_price - exit_price
    return exit_price - entry_price


def _build_summary(equity_curve: list[dict], trades: list[dict]) -> BacktestSummary:
    final_equity = equity_curve[-1]['equity'] if equity_curve else INITIAL_EQUITY
    total_return_pct = ((final_equity - INITIAL_EQUITY) / INITIAL_EQUITY) * 100 if INITIAL_EQUITY else 0.0

    wins = sum(1 for trade in trades if trade['pnl'] > 0)
    win_rate_pct = (wins / len(trades) * 100) if trades else 0.0

    peak = INITIAL_EQUITY
    max_drawdown_pct = 0.0
    for point in equity_curve:
        peak = max(peak, point['equity'])
        if peak <= 0:
            continue
        drawdown_pct = ((point['equity'] - peak) / peak) * 100
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)

    return BacktestSummary(
        total_return_pct=round(total_return_pct, 2),
        trade_count=len(trades),
        win_rate_pct=round(win_rate_pct, 2),
        max_drawdown_pct=round(max_drawdown_pct, 2),
    )
