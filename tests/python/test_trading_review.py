import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python_service.app.db import kline_db
from python_service.app.routes.trading_review import router as trading_review_router


@pytest.fixture
def review_client(tmp_path, monkeypatch):
    db_file = str(tmp_path / 'kline_test.db')
    monkeypatch.setattr(kline_db, '_db_path', lambda: db_file)
    kline_db.init_db()

    app = FastAPI()
    app.include_router(trading_review_router)
    return TestClient(app)


def test_trading_review_lifecycle_and_tp_auto_trigger(review_client):
    # 1. Seed historical K-lines
    kline_db.save_klines(
        'XAUUSD',
        'M15',
        [
            {'time': 1700000000, 'open': 2000.0, 'high': 2005.0, 'low': 1995.0, 'close': 2000.0, 'tick_volume': 100},
            {'time': 1700000900, 'open': 2000.0, 'high': 2025.0, 'low': 1998.0, 'close': 2022.0, 'tick_volume': 120},
            {'time': 1700001800, 'open': 2022.0, 'high': 2030.0, 'low': 2018.0, 'close': 2028.0, 'tick_volume': 110},
        ]
    )

    # 2. Create session
    create_res = review_client.post('/trading-review/sessions', json={
        'symbol': 'XAUUSD',
        'timeframe': 'M15',
        'start_at': '2023-11-14T22:13:20Z',
        'end_at': '2023-11-14T23:00:00Z',
        'initial_balance': 10000.0
    })
    assert create_res.status_code == 200
    session_id = create_res.json()['session_id']

    # 3. Open Buy Trade with SL=1990, TP=2020
    trade_res = review_client.post(f'/trading-review/sessions/{session_id}/trade', json={
        'type': 'buy',
        'open_price': 2000.0,
        'lots': 0.1,
        'open_time': 1700000000,
        'sl': 1990.0,
        'tp': 2020.0
    })
    assert trade_res.status_code == 200
    trade_id = trade_res.json()['trade_id']

    # 4. Step to next candle (High reaches 2025 >= TP 2020)
    next_res = review_client.post(f'/trading-review/sessions/{session_id}/next', json={'limit': 1})
    assert next_res.status_code == 200
    next_data = next_res.json()
    assert len(next_data['klines']) == 1
    assert next_data['finished'] is False
    
    # Verified triggered auto-close trades
    assert 'triggered_trades' in next_data
    assert len(next_data['triggered_trades']) == 1
    assert next_data['triggered_trades'][0]['id'] == trade_id
    assert next_data['triggered_trades'][0]['close_price'] == 2020.0
    # XAUUSD: 1 lot = 100 oz. 0.1 lot * (2020 - 2000) * 100 = $200.0
    assert pytest.approx(next_data['triggered_trades'][0]['profit'], 0.01) == 200.0

    # 5. Check session state
    state_res = review_client.get(f'/trading-review/sessions/{session_id}/state')
    assert state_res.status_code == 200
    state = state_res.json()
    assert pytest.approx(state['session']['current_balance'], 0.01) == 10200.0
    assert state['trades'][0]['close_time'] == 1700000900
    assert state['trades'][0]['profit'] == 200.0


def test_trading_review_sell_sl_auto_trigger(review_client):
    # 1. Seed historical K-lines
    kline_db.save_klines(
        'EURUSD',
        'H1',
        [
            {'time': 1700000000, 'open': 1.0800, 'high': 1.0810, 'low': 1.0790, 'close': 1.0800, 'tick_volume': 100},
            {'time': 1700003600, 'open': 1.0800, 'high': 1.0860, 'low': 1.0795, 'close': 1.0850, 'tick_volume': 150},
        ]
    )

    create_res = review_client.post('/trading-review/sessions', json={
        'symbol': 'EURUSD',
        'timeframe': 'H1',
        'start_at': '2023-11-14T22:13:20Z',
        'end_at': '2023-11-15T02:00:00Z',
        'initial_balance': 5000.0
    })
    session_id = create_res.json()['session_id']

    # Open Sell Trade with SL=1.0840, TP=1.0700
    trade_res = review_client.post(f'/trading-review/sessions/{session_id}/trade', json={
        'type': 'sell',
        'open_price': 1.0800,
        'lots': 0.1,
        'open_time': 1700000000,
        'sl': 1.0840,
        'tp': 1.0700
    })
    assert trade_res.status_code == 200

    # Step next candle (High is 1.0860 >= SL 1.0840)
    next_res = review_client.post(f'/trading-review/sessions/{session_id}/next', json={'limit': 1})
    assert next_res.status_code == 200
    triggered = next_res.json().get('triggered_trades', [])
    assert len(triggered) == 1
    assert triggered[0]['close_price'] == 1.0840
    # EURUSD contract size = 100,000. 0.1 lot * (1.0800 - 1.0840) * 100,000 = -40.0
    assert pytest.approx(triggered[0]['profit'], 0.01) == -40.0


def test_trading_review_manual_close_and_delete_session(review_client):
    kline_db.save_klines(
        'BTCUSD',
        'M5',
        [
            {'time': 1700000000, 'open': 60000.0, 'high': 60100.0, 'low': 59900.0, 'close': 60000.0, 'tick_volume': 100},
            {'time': 1700000300, 'open': 60000.0, 'high': 61000.0, 'low': 60000.0, 'close': 60800.0, 'tick_volume': 100},
        ]
    )

    create_res = review_client.post('/trading-review/sessions', json={
        'symbol': 'BTCUSD',
        'timeframe': 'M5',
        'start_at': '2023-11-14T22:13:20Z',
        'end_at': '2023-11-15T00:00:00Z',
        'initial_balance': 10000.0
    })
    session_id = create_res.json()['session_id']

    trade_res = review_client.post(f'/trading-review/sessions/{session_id}/trade', json={
        'type': 'buy',
        'open_price': 60000.0,
        'lots': 0.5,
        'open_time': 1700000000
    })
    trade_id = trade_res.json()['trade_id']

    # Advance candle
    review_client.post(f'/trading-review/sessions/{session_id}/next', json={'limit': 1})

    # Manual close at 60800
    close_res = review_client.post(f'/trading-review/sessions/{session_id}/close', json={
        'trade_id': trade_id,
        'close_price': 60800.0,
        'close_time': 1700000300
    })
    assert close_res.status_code == 200
    # BTCUSD contract size = 1. 0.5 * (60800 - 60000) * 1 = $400.0
    assert pytest.approx(close_res.json()['profit'], 0.01) == 400.0
    assert pytest.approx(close_res.json()['new_balance'], 0.01) == 10400.0

    # Delete session
    del_res = review_client.delete(f'/trading-review/sessions/{session_id}')
    assert del_res.status_code == 200

    sessions_res = review_client.get('/trading-review/sessions')
    assert len(sessions_res.json()) == 0
