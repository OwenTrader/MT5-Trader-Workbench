from collections import namedtuple

from python_service.app.local_copy_trading import source_adapter
from python_service.app.local_copy_trading.models import LocalCopyTradingState, SourceAccount


Position = namedtuple('Position', ['ticket', 'symbol', 'type', 'volume'])


def test_source_adapter_reads_real_mt5_terminal_positions(monkeypatch):
    state = LocalCopyTradingState(
        source_accounts=[
            SourceAccount(
                id='src-1',
                name='Main A',
                connection_type='mt5_terminal',
                terminal_path='C:/MT5/source/terminal64.exe',
                login='1001',
                password='secret',
                server='Demo',
            ),
        ],
    )
    calls = {'shutdown': 0}

    class FakeMT5:
        def positions_get(self):
            return [Position(ticket=123, symbol='XAUUSD.m', type=0, volume=0.2)]

    monkeypatch.setattr(source_adapter, 'mt5', FakeMT5())
    monkeypatch.setattr(source_adapter, 'init_mt5_account', lambda *args: (True, None))
    monkeypatch.setattr(source_adapter, 'shutdown_mt5', lambda: calls.__setitem__('shutdown', calls['shutdown'] + 1))

    positions = source_adapter.get_source_positions(state)

    assert positions == [
        {
            'ticket': 123,
            'symbol': 'XAUUSD.m',
            'type': 0,
            'volume': 0.2,
            'source_account_id': 'src-1',
            'position_id': '123',
        },
    ]
    assert calls['shutdown'] == 1


def test_source_adapter_reports_source_connection_failure(monkeypatch):
    state = LocalCopyTradingState(
        source_accounts=[SourceAccount(id='src-1', name='Main A', connection_type='mt5_terminal')],
    )
    monkeypatch.setattr(source_adapter, 'init_mt5_account', lambda *args: (False, 'source login failed'))

    try:
        source_adapter.get_source_positions(state)
    except RuntimeError as error:
        assert str(error) == 'source login failed'
    else:
        raise AssertionError('Expected RuntimeError')
