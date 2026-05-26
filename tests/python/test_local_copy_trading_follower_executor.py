from collections import namedtuple

from python_service.app.local_copy_trading import follower_executor
from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount


Tick = namedtuple('Tick', ['ask', 'bid'])
SymbolInfo = namedtuple('SymbolInfo', ['volume_min', 'volume_step'])
OrderResult = namedtuple('OrderResult', ['retcode', 'order', 'deal', 'comment'])
Position = namedtuple('Position', ['ticket', 'identifier', 'symbol', 'type', 'volume'])


def test_follower_executor_sends_mapped_market_order(monkeypatch):
    sent_requests = []

    class FakeMT5:
        POSITION_TYPE_BUY = 0
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        TRADE_ACTION_DEAL = 1
        ORDER_TIME_GTC = 0
        ORDER_FILLING_IOC = 1
        TRADE_RETCODE_DONE = 10009
        TRADE_RETCODE_PLACED = 10008

        def symbol_select(self, symbol, enabled):
            return symbol == 'XAUUSD.m' and enabled is True

        def symbol_info(self, symbol):
            return SymbolInfo(volume_min=0.01, volume_step=0.01)

        def symbol_info_tick(self, symbol):
            return Tick(ask=2301.5, bid=2301.3)

        def order_send(self, request):
            sent_requests.append(request)
            return OrderResult(retcode=10009, order=456, deal=0, comment='done')

        def positions_get(self, symbol=None):
            return [Position(ticket=789, identifier=456, symbol='XAUUSD.m', type=0, volume=0.2)]

        def last_error(self):
            return (0, 'ok')

    monkeypatch.setattr(follower_executor, 'mt5', FakeMT5())
    monkeypatch.setattr(follower_executor, 'init_mt5_account', lambda *args: (True, None))
    monkeypatch.setattr(follower_executor, 'shutdown_mt5', lambda: None)

    success, message, follower_position_id, follower_order_id = follower_executor.copy_position_to_follower(
        FollowerAccount(
            id='fol-1',
            name='Follower A',
            connection_type='mt5_terminal',
            terminal_path='D:/MT5/follower/terminal64.exe',
            login='2001',
            password='secret',
            server='Demo',
        ),
        CopyRelationship(
            id='rel-1',
            source_account_id='src-1',
            follower_account_id='fol-1',
            source_symbol='XAUUSD',
            follower_symbol='XAUUSD.m',
            lot_multiplier=2,
        ),
        {'type': 0, 'volume': 0.1},
    )

    assert success is True
    assert 'order 456' in message
    assert sent_requests[0]['symbol'] == 'XAUUSD.m'
    assert sent_requests[0]['volume'] == 0.2
    assert sent_requests[0]['type'] == 0
    assert sent_requests[0]['price'] == 2301.5
    assert follower_position_id == '789'
    assert follower_order_id == '456'


def test_follower_executor_returns_failure_when_order_send_fails(monkeypatch):
    class FakeMT5:
        POSITION_TYPE_BUY = 0
        ORDER_TYPE_BUY = 0
        TRADE_ACTION_DEAL = 1
        ORDER_TIME_GTC = 0
        ORDER_FILLING_IOC = 1
        TRADE_RETCODE_DONE = 10009
        TRADE_RETCODE_PLACED = 10008

        def symbol_select(self, symbol, enabled):
            return True

        def symbol_info(self, symbol):
            return SymbolInfo(volume_min=0.01, volume_step=0.01)

        def symbol_info_tick(self, symbol):
            return Tick(ask=2301.5, bid=2301.3)

        def order_send(self, request):
            return OrderResult(retcode=10030, order=0, deal=0, comment='market closed')

        def last_error(self):
            return (0, 'ok')

    monkeypatch.setattr(follower_executor, 'mt5', FakeMT5())
    monkeypatch.setattr(follower_executor, 'init_mt5_account', lambda *args: (True, None))
    monkeypatch.setattr(follower_executor, 'shutdown_mt5', lambda: None)

    success, message, follower_position_id, follower_order_id = follower_executor.copy_position_to_follower(
        FollowerAccount(id='fol-1', name='Follower A', connection_type='mt5_terminal'),
        CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', source_symbol='XAUUSD', follower_symbol='XAUUSD.m'),
        {'type': 0, 'volume': 0.1},
    )

    assert success is False
    assert 'market closed' in message
    assert follower_position_id == ''
    assert follower_order_id == ''


def test_follower_executor_rejects_zero_effective_volume(monkeypatch):
    class FakeMT5:
        POSITION_TYPE_BUY = 0

        def symbol_select(self, symbol, enabled):
            return True

        def symbol_info(self, symbol):
            return SymbolInfo(volume_min=0.01, volume_step=0.01)

        def symbol_info_tick(self, symbol):
            return Tick(ask=2301.5, bid=2301.3)

        def last_error(self):
            return (0, 'ok')

    monkeypatch.setattr(follower_executor, 'mt5', FakeMT5())
    monkeypatch.setattr(follower_executor, 'init_mt5_account', lambda *args: (True, None))
    monkeypatch.setattr(follower_executor, 'shutdown_mt5', lambda: None)

    success, message, follower_position_id, follower_order_id = follower_executor.copy_position_to_follower(
        FollowerAccount(id='fol-1', name='Follower A', connection_type='mt5_terminal'),
        CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', source_symbol='XAUUSD', follower_symbol='XAUUSD.m'),
        {'type': 0, 'volume': 0},
    )

    assert success is False
    assert message == 'copy volume must be greater than 0'
    assert follower_position_id == ''
    assert follower_order_id == ''


def test_follower_executor_closes_copied_position(monkeypatch):
    sent_requests = []

    class FakeMT5:
        POSITION_TYPE_BUY = 0
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        TRADE_ACTION_DEAL = 1
        ORDER_TIME_GTC = 0
        ORDER_FILLING_IOC = 1
        TRADE_RETCODE_DONE = 10009
        TRADE_RETCODE_PLACED = 10008

        def positions_get(self, symbol=None):
            return [Position(ticket=789, identifier=456, symbol='XAUUSD.m', type=0, volume=0.2)]

        def symbol_select(self, symbol, enabled):
            return symbol == 'XAUUSD.m' and enabled is True

        def symbol_info_tick(self, symbol):
            return Tick(ask=2301.5, bid=2301.3)

        def order_send(self, request):
            sent_requests.append(request)
            return OrderResult(retcode=10009, order=999, deal=0, comment='closed')

        def last_error(self):
            return (0, 'ok')

    monkeypatch.setattr(follower_executor, 'mt5', FakeMT5())
    monkeypatch.setattr(follower_executor, 'init_mt5_account', lambda *args: (True, None))
    monkeypatch.setattr(follower_executor, 'shutdown_mt5', lambda: None)

    success, message = follower_executor.close_copied_position_on_follower(
        FollowerAccount(id='fol-1', name='Follower A', connection_type='mt5_terminal'),
        CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', source_symbol='XAUUSD', follower_symbol='XAUUSD.m'),
        follower_executor.SyncEvent(
            relationship_id='rel-1',
            source_account_id='src-1',
            follower_account_id='fol-1',
            position_id='pos-1',
            follower_position_id='789',
            follower_order_id='456',
            symbol='XAUUSD.m',
            status='copied',
            created_at='2026-05-26T00:00:00+00:00',
        ),
    )

    assert success is True
    assert 'Closed follower position 789' in message
    assert sent_requests[0]['position'] == 789
    assert sent_requests[0]['type'] == 1
    assert sent_requests[0]['volume'] == 0.2
    assert sent_requests[0]['price'] == 2301.3


def test_follower_executor_treats_missing_position_as_already_closed(monkeypatch):
    class FakeMT5:
        def positions_get(self, symbol=None):
            return []

    monkeypatch.setattr(follower_executor, 'mt5', FakeMT5())
    monkeypatch.setattr(follower_executor, 'init_mt5_account', lambda *args: (True, None))
    monkeypatch.setattr(follower_executor, 'shutdown_mt5', lambda: None)

    success, message = follower_executor.close_copied_position_on_follower(
        FollowerAccount(id='fol-1', name='Follower A', connection_type='mt5_terminal'),
        CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', source_symbol='XAUUSD', follower_symbol='XAUUSD.m'),
        follower_executor.SyncEvent(
            relationship_id='rel-1',
            source_account_id='src-1',
            follower_account_id='fol-1',
            position_id='pos-1',
            follower_position_id='789',
            symbol='XAUUSD.m',
            status='copied',
            created_at='2026-05-26T00:00:00+00:00',
        ),
    )

    assert success is True
    assert 'already closed' in message
