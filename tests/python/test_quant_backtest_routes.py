from fastapi import FastAPI
from fastapi.testclient import TestClient

from python_service.app.local_copy_trading.models import LocalCopyTradingState, SourceAccount
from python_service.app.local_copy_trading.runtime import reset_state
from python_service.app.quant.backtest_routes import router as quant_backtest_router


def build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(quant_backtest_router)
    return app


def seed_accounts() -> None:
    reset_state(
        LocalCopyTradingState(
            accounts=[
                SourceAccount(
                    id='acc-1',
                    name='Main A',
                    connection_type='mt5_terminal',
                    terminal_path='C:/MT5/terminal64.exe',
                    login='1001',
                    server='demo',
                    password='secret',
                    is_active=True,
                )
            ]
        )
    )


def test_backtest_strategies_route_returns_unified_strategy_list():
    seed_accounts()
    client = TestClient(build_test_app())

    response = client.get('/python-quant/backtests/strategies')

    assert response.status_code == 200
    assert any(item['id'] == 'sma_cross' for item in response.json())


def test_backtest_run_route_returns_summary_payload(monkeypatch):
    seed_accounts()
    client = TestClient(build_test_app())
    monkeypatch.setattr(
        'python_service.app.quant.backtest_routes.run_backtest',
        lambda **kwargs: {'summary': {'trade_count': 1}, 'trades': [], 'equity_curve': []},
    )

    response = client.post('/python-quant/backtests/run', json={
        'strategy_id': 'sma_cross',
        'account_id': 'acc-1',
        'symbol': 'XAUUSD',
        'timeframe': 'M15',
        'start_at': '2026-05-01T00:00:00Z',
        'end_at': '2026-05-31T23:59:59Z',
    })

    assert response.status_code == 200
    assert response.json()['summary']['trade_count'] == 1
