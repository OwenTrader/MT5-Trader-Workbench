from collections import namedtuple

from python_service.app.local_copy_trading import follower_executor, position_ownership
from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount


Tick = namedtuple('Tick', ['ask', 'bid'])
SymbolInfo = namedtuple('SymbolInfo', ['volume_min', 'volume_step', 'digits'])
OrderResult = namedtuple('OrderResult', ['retcode', 'order', 'deal', 'comment'])
Position = namedtuple('Position', ['ticket', 'identifier', 'symbol', 'type', 'volume', 'magic', 'comment'])


def _follower(**overrides):
    fields = {
        'id': 'fol-1',
        'name': 'Follower A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'D:/MT5/follower/terminal64.exe',
        'login': '2001',
        'password': 'secret',
        'server': 'Demo',
    }
    fields.update(overrides)
    return FollowerAccount(**fields)


def _relationship(**overrides):
    fields = {
        'id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'symbol': 'XAUUSD',
        'source_symbol': 'XAUUSD',
        'follower_symbol': 'XAUUSD.m',
    }
    fields.update(overrides)
    return CopyRelationship(**fields)


def _owned_position(ticket=789, position_id='pos-1', relationship_id='rel-1', **overrides):
    fields = {
        'ticket': ticket,
        'identifier': ticket,
        'symbol': 'XAUUSD.m',
        'type': 0,
        'volume': 0.2,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment(relationship_id, position_id),
    }
    fields.update(overrides)
    return Position(**fields)


def _copied_event(**overrides):
    fields = {
        'relationship_id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'position_id': 'pos-1',
        'follower_position_id': '789',
        'follower_order_id': '456',
        'symbol': 'XAUUSD.m',
        'status': 'copied',
        'created_at': '2026-09-18T00:00:00+00:00',
    }
    fields.update(overrides)
    return follower_executor.SyncEvent(**fields)


class FakeClient:
    POSITION_TYPE_BUY = 0
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008

    def __init__(self, positions=None):
        self.sent_requests = []
        self._positions = positions if positions is not None else []

    def symbol_select(self, symbol, enabled):
        return enabled is True

    def symbol_info(self, symbol):
        return SymbolInfo(volume_min=0.01, volume_step=0.01, digits=2)

    def symbol_info_tick(self, symbol):
        return Tick(ask=2301.5, bid=2301.3)

    def order_send(self, request):
        self.sent_requests.append(request)
        return OrderResult(retcode=10009, order=456, deal=0, comment='done')

    def positions_get(self, symbol=None):
        return self._positions

    def last_error(self):
        return (0, 'ok')


def test_copy_position_tags_the_order_with_an_ownership_comment():
    client = FakeClient()

    follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(lot_multiplier=2),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    request = client.sent_requests[0]
    assert request['symbol'] == 'XAUUSD.m'
    assert request['volume'] == 0.2
    assert request['magic'] == position_ownership.COPY_TRADING_MAGIC
    assert request['comment'] == position_ownership.build_comment('rel-1', 'pos-1')
    assert len(request['comment']) <= position_ownership.MAX_COMMENT_LENGTH


def test_copy_position_reports_the_owned_follower_ticket():
    client = FakeClient(positions=[_owned_position(ticket=789)])

    success, message, follower_position_id, follower_order_id = follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is True
    assert follower_position_id == '789'
    assert follower_order_id == '456'


def test_copy_position_leaves_the_ticket_empty_when_ownership_cannot_be_confirmed():
    client = FakeClient(positions=[_owned_position(ticket=999, position_id='pos-9')])

    success, message, follower_position_id, _ = follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is True
    assert follower_position_id == ''


def test_copy_position_reports_symbol_selection_failure():
    class FailingClient(FakeClient):
        def symbol_select(self, symbol, enabled):
            return False

    success, message, _, _ = follower_executor.copy_position_to_follower(
        FailingClient(),
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is False
    assert 'Failed to select follower symbol' in message


def test_copy_position_runs_without_a_follower_connection_for_simulated_accounts():
    success, message, follower_position_id, _ = follower_executor.copy_position_to_follower(
        None,
        _follower(connection_type='simulated'),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is True
    assert follower_position_id == 'pos-1'
    assert 'Simulated copy' in message


def test_copy_position_rejects_unsupported_connection_types():
    success, message, _, _ = follower_executor.copy_position_to_follower(
        None,
        _follower(connection_type='mt5_api'),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is False
    assert 'Unsupported follower connection type' in message


def test_close_position_closes_only_the_owned_position():
    client = FakeClient(
        positions=[
            _owned_position(ticket=111, position_id='pos-9'),
            Position(ticket=222, identifier=222, symbol='XAUUSD.m', type=0, volume=0.5, magic=0, comment=''),
            _owned_position(ticket=789, position_id='pos-1', volume=0.2),
        ]
    )

    success, message = follower_executor.close_copied_position_on_follower(
        client,
        _follower(),
        _relationship(),
        _copied_event(),
    )

    assert success is True
    assert len(client.sent_requests) == 1
    request = client.sent_requests[0]
    assert request['position'] == 789
    assert request['volume'] == 0.2
    assert request['type'] == FakeClient.ORDER_TYPE_SELL


def test_close_position_does_not_send_an_order_when_nothing_is_owned():
    client = FakeClient(
        positions=[
            Position(ticket=222, identifier=222, symbol='XAUUSD.m', type=0, volume=0.5, magic=0, comment=''),
            _owned_position(ticket=111, position_id='pos-9'),
        ]
    )

    success, message = follower_executor.close_copied_position_on_follower(
        client,
        _follower(),
        _relationship(),
        _copied_event(),
    )

    assert success is True
    assert client.sent_requests == []
    assert 'nothing to close' in message


def test_close_position_requires_the_relationship_to_match():
    client = FakeClient(positions=[_owned_position(ticket=789, relationship_id='rel-2')])

    success, message = follower_executor.close_copied_position_on_follower(
        client,
        _follower(),
        _relationship(),
        _copied_event(),
    )

    assert success is True
    assert client.sent_requests == []


def test_copy_position_leaves_protective_levels_unset_by_default():
    client = FakeClient()

    follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(),
        {
            'position_id': 'pos-1',
            'symbol': 'XAUUSD',
            'volume': 0.1,
            'type': 0,
            'price_open': 2300.0,
            'sl': 2280.0,
            'tp': 2340.0,
        },
    )

    request = client.sent_requests[0]
    assert request['sl'] == 0.0
    assert request['tp'] == 0.0


def test_copy_position_translates_protective_levels_when_enabled():
    client = FakeClient()

    follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(sync_sl_tp=True),
        {
            'position_id': 'pos-1',
            'symbol': 'XAUUSD',
            'volume': 0.1,
            'type': 0,
            'price_open': 2300.0,
            'sl': 2280.0,
            'tp': 2340.0,
        },
    )

    request = client.sent_requests[0]
    # The buy fills at the ask (2301.5), so the source distances of 20 and 40 carry over.
    assert request['sl'] == 2281.5
    assert request['tp'] == 2341.5


def test_copy_position_uses_the_fixed_volume_mode():
    client = FakeClient()

    follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(volume_mode='fixed', lot_multiplier=0.3),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.9, 'type': 0},
    )

    assert client.sent_requests[0]['volume'] == 0.3


def test_copy_position_reports_a_sizing_failure_as_a_failed_copy():
    client = FakeClient()

    success, message, _, _ = follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(volume_mode='risk_percent'),
        {
            'position_id': 'pos-1',
            'symbol': 'XAUUSD',
            'volume': 0.1,
            'type': 0,
            'price_open': 2300.0,
            'sl': 0.0,
            'source_equity': 10000.0,
        },
    )

    assert success is False
    assert 'requires a source position with a stop loss' in message
    assert client.sent_requests == []


def test_copy_position_scales_by_equity_when_the_follower_reports_equity():
    class EquityClient(FakeClient):
        def account_info(self):
            return namedtuple('AccountInfo', ['equity'])(equity=2500.0)

    client = EquityClient()

    follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(volume_mode='equity_ratio'),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.4, 'type': 0, 'source_equity': 10000.0},
    )

    assert client.sent_requests[0]['volume'] == 0.1


def _source(**overrides):
    fields = {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.2, 'type': 0}
    fields.update(overrides)
    return fields


def test_adjust_partially_closes_when_the_follower_is_too_large():
    client = FakeClient(positions=[_owned_position(volume=0.3)])

    success, message = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.1
    )

    assert success is True
    request = client.sent_requests[0]
    assert request['position'] == 789
    assert request['volume'] == 0.2
    assert request['type'] == FakeClient.ORDER_TYPE_SELL
    assert 'Partially closed' in message


def test_adjust_scales_in_when_the_follower_is_too_small():
    client = FakeClient(positions=[_owned_position(volume=0.1)])

    success, message = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.3
    )

    assert success is True
    request = client.sent_requests[0]
    assert 'position' not in request
    assert request['volume'] == 0.2
    assert request['type'] == FakeClient.ORDER_TYPE_BUY
    assert 'Scaled in' in message


def test_adjust_reverses_the_direction_for_a_short_position():
    client = FakeClient(positions=[_owned_position(type=1, volume=0.3)])

    follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(type=1), expected_volume=0.1
    )

    request = client.sent_requests[0]
    assert request['type'] == FakeClient.ORDER_TYPE_BUY
    assert request['volume'] == 0.2


def test_adjust_sends_nothing_when_the_volume_already_matches():
    client = FakeClient(positions=[_owned_position(volume=0.2)])

    success, message = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.2
    )

    assert success is True
    assert client.sent_requests == []
    assert 'already matches' in message


def test_adjust_ignores_a_difference_smaller_than_one_step():
    client = FakeClient(positions=[_owned_position(volume=0.2)])

    success, _ = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.205
    )

    assert success is True
    assert client.sent_requests == []


def test_adjust_fails_when_no_position_is_owned():
    client = FakeClient(positions=[Position(222, 222, 'XAUUSD.m', 0, 0.5, 0, '')])

    success, message = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.1
    )

    assert success is False
    assert 'No owned follower position' in message
    assert client.sent_requests == []


def test_adjust_reports_a_broker_rejection():
    class RejectingClient(FakeClient):
        def order_send(self, request):
            self.sent_requests.append(request)
            return OrderResult(retcode=10006, order=0, deal=0, comment='rejected')

    client = RejectingClient(positions=[_owned_position(volume=0.3)])

    success, message = follower_executor.adjust_copied_position_volume(
        client, _follower(), _relationship(), _source(), expected_volume=0.1
    )

    assert success is False
    assert 'Retcode: 10006' in message


def test_adjust_is_a_no_op_for_simulated_followers():
    success, message = follower_executor.adjust_copied_position_volume(
        None, _follower(connection_type='simulated'), _relationship(), _source(), expected_volume=0.1
    )

    assert success is True
    assert 'Simulated volume sync' in message


def test_plan_copy_order_exposes_the_size_before_anything_is_sent():
    client = FakeClient()

    plan = follower_executor.plan_copy_order(
        client, _follower(), _relationship(lot_multiplier=3), _source(volume=0.1)
    )

    assert plan.ok is True
    assert plan.volume == 0.3
    assert plan.request['volume'] == 0.3
    assert client.sent_requests == []


def test_plan_copy_order_reports_a_missing_symbol_without_sending():
    class NoSelectClient(FakeClient):
        def symbol_select(self, symbol, enabled):
            return False

    plan = follower_executor.plan_copy_order(
        NoSelectClient(), _follower(), _relationship(), _source()
    )

    assert plan.ok is False
    assert plan.request is None
    assert 'Failed to select follower symbol' in plan.message
