import pytest

from python_service.app.quant.backtest_service import run_backtest
from python_service.app.quant.market_data import load_bars_for_range
from python_service.app.services import mt5_service


def _build_sma_cross_bars() -> list[dict]:
    bars: list[dict] = []
    closes = ([100.0] * 30) + ([110.0] * 15) + ([100.0] * 15)

    for index, close in enumerate(closes):
        hour = index // 4
        minute = (index % 4) * 15
        bars.append({
            'time': f'2026-05-01T{hour:02d}:{minute:02d}:00+00:00',
            'open': close,
            'high': close + 1.0,
            'low': close - 1.0,
            'close': close,
            'tick_volume': 100 + index,
        })

    return bars


def test_run_backtest_returns_summary_and_trades(monkeypatch):
    bars = _build_sma_cross_bars()
    monkeypatch.setattr(
        'python_service.app.quant.backtest_service.load_bars_for_range',
        lambda **kwargs: bars,
    )
    monkeypatch.setattr(
        'python_service.app.quant.backtest_service._evaluate_strategy_signals',
        lambda strategy_id, rows: (['hold'] * 30) + (['buy'] * 15) + (['close'] * 15),
    )

    result = run_backtest(
        account_id='acc-1',
        strategy_id='sma_cross',
        symbol='XAUUSD',
        timeframe='M15',
        start_at='2026-05-01T00:00:00Z',
        end_at='2026-05-31T23:59:59Z',
    )

    assert result['strategy']['id'] == 'sma_cross'
    assert result['summary']['trade_count'] == 1
    assert result['trades'][0]['side'] == 'buy'
    assert len(result['equity_curve']) == 60


def test_run_backtest_raises_when_no_bars_are_available(monkeypatch):
    monkeypatch.setattr('python_service.app.quant.backtest_service.load_bars_for_range', lambda **kwargs: [])

    with pytest.raises(ValueError, match='No cached bars available for the requested range'):
        run_backtest(
            account_id='acc-1',
            strategy_id='sma_cross',
            symbol='XAUUSD',
            timeframe='M15',
            start_at='2026-05-01T00:00:00Z',
            end_at='2026-05-31T23:59:59Z',
        )


def test_load_bars_for_range_backfills_missing_range_for_account(tmp_path, monkeypatch):
    fetched = {}
    monkeypatch.setattr(
        'python_service.app.quant.market_data._get_runtime_account',
        lambda account_id: {
            'id': account_id,
            'terminal_path': 'C:/MT5/terminal64.exe',
            'login': '1001',
            'password': 'secret',
            'server': 'demo',
        },
    )

    def fake_fetch_account_bars_range(**kwargs):
        fetched['request'] = kwargs
        return [
            {
                'time': '2026-05-01T00:00:00+00:00',
                'open': 1.0,
                'high': 2.0,
                'low': 0.5,
                'close': 1.5,
                'tick_volume': 10,
            },
            {
                'time': '2026-05-01T00:15:00+00:00',
                'open': 1.5,
                'high': 2.5,
                'low': 1.0,
                'close': 2.0,
                'tick_volume': 11,
            },
        ]

    monkeypatch.setattr('python_service.app.quant.market_data.fetch_account_bars_range', fake_fetch_account_bars_range)

    loaded = load_bars_for_range(
        tmp_path / 'market_data.sqlite3',
        'acc-1',
        'XAUUSD',
        'M15',
        '2026-05-01T00:00:00Z',
        '2026-05-01T00:15:00Z',
    )

    assert fetched['request']['login'] == '1001'
    assert fetched['request']['start_at'] == '2026-05-01T00:00:00+00:00'
    assert len(loaded) == 2


def test_fetch_account_bars_range_uses_mt5_date_range_api(monkeypatch):
    captured = {}

    class FakeMT5:
        TIMEFRAME_M15 = 15

        def copy_rates_range(self, symbol, timeframe, date_from, date_to):
            captured['symbol'] = symbol
            captured['timeframe'] = timeframe
            captured['date_from'] = date_from
            captured['date_to'] = date_to
            return [
                {
                    'time': 1710000000,
                    'open': 1.1,
                    'high': 1.2,
                    'low': 1.0,
                    'close': 1.15,
                    'tick_volume': 123,
                }
            ]

    monkeypatch.setattr(mt5_service, 'mt5', FakeMT5())
    monkeypatch.setattr(mt5_service, '_init_mt5_account_unlocked', lambda *args, **kwargs: (True, None))

    bars = mt5_service.fetch_account_bars_range(
        'C:/MT5/terminal64.exe',
        '1001',
        'secret',
        'Demo-Server',
        'XAUUSD',
        'M15',
        '2026-05-01T00:00:00Z',
        '2026-05-31T23:59:59Z',
    )

    assert captured['symbol'] == 'XAUUSD'
    assert captured['date_from'].isoformat() == '2026-05-01T00:00:00+00:00'
    assert captured['date_to'].isoformat() == '2026-05-31T23:59:59+00:00'
    assert bars[0]['tick_volume'] == 123
