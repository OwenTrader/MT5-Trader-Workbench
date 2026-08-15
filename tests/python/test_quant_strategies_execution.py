from datetime import datetime, timedelta, timezone
import pytest

from python_service.app.quant.runtime import evaluate_strategy_signal
from python_service.app.quant.strategy_registry import list_strategies, get_strategy_module


def generate_sample_bars(n: int = 60, start_price: float = 100.0) -> list[dict]:
    bars = []
    base_time = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    price = start_price
    for i in range(n):
        delta = (i % 5 - 2) * 1.5
        open_p = price
        close_p = price + delta
        high_p = max(open_p, close_p) + 1.0
        low_p = min(open_p, close_p) - 1.0
        price = close_p
        bars.append({
            'time': (base_time + timedelta(minutes=15 * i)).isoformat(),
            'open': open_p,
            'high': high_p,
            'low': low_p,
            'close': close_p,
            'tick_volume': 100 + i * 2,
        })
    return bars


@pytest.mark.parametrize('strategy_id', [
    'sma_cross',
    'rsi_reversal',
    'macd_trend',
    'bollinger_breakout',
    'dual_thrust',
    'turtle_donchian',
])
def test_strategy_descriptors_and_signal_evaluation(strategy_id):
    strategies = list_strategies()
    strategy_ids = [s.id for s in strategies]
    assert strategy_id in strategy_ids

    module = get_strategy_module(strategy_id)
    assert hasattr(module, 'STRATEGY_ID')
    assert hasattr(module, 'STRATEGY_NAME')
    assert hasattr(module, 'STRATEGY_DESCRIPTION')
    assert hasattr(module, 'SUPPORTED_TIMEFRAMES')
    assert hasattr(module, 'Strategy')

    bars = generate_sample_bars(n=60)
    signal, latest_bar_time = evaluate_strategy_signal(strategy_id, bars)
    assert signal in {'buy', 'sell', 'close', 'hold'}
    assert latest_bar_time == bars[-1]['time']
