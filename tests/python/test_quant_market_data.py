from python_service.app.quant.market_data import backfill_from_mt5, load_recent_bars, upsert_bars


def test_upsert_bars_round_trips_sqlite_rows(tmp_path):
    db_path = tmp_path / 'market_data.sqlite3'
    bars = [
        {
            'time': '2026-06-05T08:30:00+00:00',
            'open': 3300.0,
            'high': 3302.0,
            'low': 3299.0,
            'close': 3301.0,
            'tick_volume': 100,
        }
    ]

    upsert_bars(db_path, 'acc-1', 'XAUUSD', 'M5', bars)
    loaded = load_recent_bars(db_path, 'acc-1', 'XAUUSD', 'M5', limit=1)

    assert loaded[0]['close'] == 3301.0


def test_backfill_from_mt5_persists_missing_bars(tmp_path, monkeypatch):
    monkeypatch.setattr(
        'python_service.app.quant.market_data.fetch_account_bars',
        lambda **kwargs: [
            {
                'time': '2026-06-05T08:35:00+00:00',
                'open': 1.0,
                'high': 2.0,
                'low': 0.5,
                'close': 1.5,
                'tick_volume': 10,
            }
        ],
    )

    rows = backfill_from_mt5(
        db_path=tmp_path / 'market_data.sqlite3',
        account={
            'terminal_path': 'C:/MT5/terminal64.exe',
            'login': '1001',
            'password': 'secret',
            'server': 'demo',
        },
        account_id='acc-1',
        symbol='XAUUSD',
        timeframe='M5',
        bars=1,
    )

    assert rows == 1
