import asyncio

import pytest

from python_service.app.models.order_sync import OrderSyncState, OrderSymbolMapping, SyncedOrder
from python_service.app.services import order_sync_service
from python_service.app.services.order_sync_service import (
    calculate_topstep_contract_size,
    process_order_sync_tick,
    reset_order_sync_state_for_tests,
    run_topstep_with_retries,
    should_block_high_frequency_order,
)
from python_service.app.services.topstep_service import TopStepApiError


class FakeTopStepClient:
    def __init__(self, fail_open_times=0, fail_close_times=0):
        self.fail_open_times = fail_open_times
        self.fail_close_times = fail_close_times
        self.open_calls = 0
        self.close_calls = 0

    def place_market_order(self, contract_id, side, size, custom_tag=None):
        self.open_calls += 1
        if self.open_calls <= self.fail_open_times:
            raise TopStepApiError('temporary open failure')
        return 9056

    def close_contract_position(self, contract_id):
        self.close_calls += 1
        if self.close_calls <= self.fail_close_times:
            raise TopStepApiError('temporary close failure')


def test_order_sync_state_defaults_disable_high_frequency_blocking():
    state = OrderSyncState()

    assert state.block_high_frequency_orders is False
    assert state.high_frequency_window_seconds == 5


def test_symbol_mapping_defaults_to_one_mt5_lot_equals_one_topstep_contract():
    mapping = OrderSymbolMapping(mt5_symbol='xauusd', topstep_contract_id='CON.F.US.GC.TEST')

    assert mapping.mt5_symbol == 'XAUUSD'
    assert mapping.mt5_lots == 1
    assert mapping.topstep_contracts == 1


def test_calculates_topstep_contract_size_from_mapping_ratio():
    mapping = OrderSymbolMapping(
        mt5_symbol='XAUUSD',
        topstep_contract_id='CON.F.US.GC.TEST',
        mt5_lots=0.1,
        topstep_contracts=1,
    )

    assert calculate_topstep_contract_size({'volume': 0.3}, mapping) == 3


def test_contract_size_is_at_least_one():
    mapping = OrderSymbolMapping(
        mt5_symbol='XAUUSD',
        topstep_contract_id='CON.F.US.GC.TEST',
        mt5_lots=10,
        topstep_contracts=1,
    )

    assert calculate_topstep_contract_size({'volume': 0.01}, mapping) == 1


def test_calculates_topstep_contract_size_from_legacy_multiplier_fallback():
    mapping = OrderSymbolMapping(
        mt5_symbol='XAUUSD',
        topstep_contract_id='CON.F.US.GC.TEST',
        quantity_multiplier=10,
    )

    assert calculate_topstep_contract_size({'volume': 0.3}, mapping) == 3


def test_explicit_ratio_overrides_stale_legacy_multiplier():
    mapping = OrderSymbolMapping(
        mt5_symbol='XAUUSD',
        topstep_contract_id='CON.F.US.GC.TEST',
        quantity_multiplier=10,
        mt5_lots=1,
        topstep_contracts=1,
    )

    assert calculate_topstep_contract_size({'volume': 0.3}, mapping) == 1


def test_topstep_operation_retries_three_times_then_succeeds():
    calls = {'count': 0}

    def flaky_operation():
        calls['count'] += 1
        if calls['count'] < 3:
            raise TopStepApiError('temporary')
        return 9056

    result = asyncio.run(run_topstep_with_retries(flaky_operation, retry_delay_seconds=0))

    assert result == 9056
    assert calls['count'] == 3


def test_topstep_operation_fails_after_three_attempts():
    calls = {'count': 0}

    def failing_operation():
        calls['count'] += 1
        raise TopStepApiError('still down')

    with pytest.raises(TopStepApiError):
        asyncio.run(run_topstep_with_retries(failing_operation, retry_delay_seconds=0))

    assert calls['count'] == 3


def test_synced_order_stores_mt5_volume_for_frequency_gate():
    order = SyncedOrder(
        mt5_ticket=1,
        mt5_symbol='XAUUSD',
        mt5_volume=0.1,
        topstep_account_id=100,
        topstep_contract_id='CON.F.US.GC.TEST',
        side='buy',
        size=1,
        opened_at='2026-05-04T00:00:00+00:00',
    )

    assert order.mt5_volume == 0.1


def test_blocks_same_symbol_side_and_volume_inside_window():
    state = OrderSyncState(block_high_frequency_orders=True, high_frequency_window_seconds=5)
    state.synced_orders = [SyncedOrder(
        mt5_ticket=1,
        mt5_symbol='XAUUSD',
        mt5_volume=0.1,
        topstep_account_id=100,
        topstep_contract_id='CON.F.US.GC.TEST',
        side='buy',
        size=1,
        opened_at='2026-05-04T00:00:00+00:00',
    )]

    assert should_block_high_frequency_order(
        state,
        symbol='XAUUSD',
        side='buy',
        mt5_volume=0.1,
        now_iso='2026-05-04T00:00:04+00:00',
    ) is True


def test_allows_same_order_after_window():
    state = OrderSyncState(block_high_frequency_orders=True, high_frequency_window_seconds=5)
    state.synced_orders = [SyncedOrder(
        mt5_ticket=1,
        mt5_symbol='XAUUSD',
        mt5_volume=0.1,
        topstep_account_id=100,
        topstep_contract_id='CON.F.US.GC.TEST',
        side='buy',
        size=1,
        opened_at='2026-05-04T00:00:00+00:00',
    )]

    assert should_block_high_frequency_order(
        state,
        symbol='XAUUSD',
        side='buy',
        mt5_volume=0.1,
        now_iso='2026-05-04T00:00:06+00:00',
    ) is False


def test_process_tick_retries_open_order(monkeypatch):
    state = OrderSyncState(
        enabled=True,
        credentials=[{
            'id': 'credential-1',
            'user_name': 'user',
            'api_key': 'key',
            'account_id': 100,
            'is_active': True,
        }],
        mappings=[{
            'id': 'mapping-1',
            'mt5_symbol': 'XAUUSD',
            'topstep_contract_id': 'CON.F.US.GC.TEST',
            'mt5_lots': 0.1,
            'topstep_contracts': 1,
            'is_active': True,
        }],
    )
    fake_client = FakeTopStepClient(fail_open_times=2)
    reset_order_sync_state_for_tests(state)
    monkeypatch.setattr(order_sync_service, 'get_positions', lambda: [{'ticket': 1, 'symbol': 'XAUUSD', 'type': 0, 'volume': 0.1}])
    monkeypatch.setattr(order_sync_service, '_get_client', lambda credential_id: fake_client)
    monkeypatch.setattr(order_sync_service, '_save', lambda: None)

    asyncio.run(process_order_sync_tick())

    assert fake_client.open_calls == 3
    assert state.synced_orders[0].topstep_order_id == 9056
    assert state.synced_orders[0].status == 'open'


def test_process_tick_retries_close_order(monkeypatch):
    state = OrderSyncState(
        enabled=True,
        credentials=[{
            'id': 'credential-1',
            'user_name': 'user',
            'api_key': 'key',
            'account_id': 100,
            'is_active': True,
        }],
        synced_orders=[SyncedOrder(
            mt5_ticket=1,
            mt5_symbol='XAUUSD',
            mt5_volume=0.1,
            topstep_account_id=100,
            topstep_contract_id='CON.F.US.GC.TEST',
            side='buy',
            size=1,
            opened_at='2026-05-04T00:00:00+00:00',
        )],
    )
    fake_client = FakeTopStepClient(fail_close_times=2)
    reset_order_sync_state_for_tests(state)
    monkeypatch.setattr(order_sync_service, 'get_positions', lambda: [])
    monkeypatch.setattr(order_sync_service, '_get_client', lambda credential_id: fake_client)
    monkeypatch.setattr(order_sync_service, '_save', lambda: None)

    asyncio.run(process_order_sync_tick())

    assert fake_client.close_calls == 3
    assert state.synced_orders[0].status == 'closed'
    assert state.synced_orders[0].closed_at is not None


def test_process_tick_blocks_high_frequency_duplicate(monkeypatch):
    state = OrderSyncState(
        enabled=True,
        block_high_frequency_orders=True,
        high_frequency_window_seconds=5,
        credentials=[{
            'id': 'credential-1',
            'user_name': 'user',
            'api_key': 'key',
            'account_id': 100,
            'is_active': True,
        }],
        mappings=[{
            'id': 'mapping-1',
            'mt5_symbol': 'XAUUSD',
            'topstep_contract_id': 'CON.F.US.GC.TEST',
            'mt5_lots': 0.1,
            'topstep_contracts': 1,
            'is_active': True,
        }],
        synced_orders=[SyncedOrder(
            mt5_ticket=1,
            mt5_symbol='XAUUSD',
            mt5_volume=0.1,
            topstep_account_id=100,
            topstep_contract_id='CON.F.US.GC.TEST',
            side='buy',
            size=1,
            opened_at='2026-05-04T00:00:00+00:00',
        )],
    )
    fake_client = FakeTopStepClient()
    reset_order_sync_state_for_tests(state)
    monkeypatch.setattr(order_sync_service, '_utc_now', lambda: '2026-05-04T00:00:04+00:00')
    monkeypatch.setattr(order_sync_service, 'get_positions', lambda: [
        {'ticket': 1, 'symbol': 'XAUUSD', 'type': 0, 'volume': 0.1},
        {'ticket': 2, 'symbol': 'XAUUSD', 'type': 0, 'volume': 0.1},
    ])
    monkeypatch.setattr(order_sync_service, '_get_client', lambda credential_id: fake_client)
    monkeypatch.setattr(order_sync_service, '_save', lambda: None)

    asyncio.run(process_order_sync_tick())

    assert fake_client.open_calls == 0
    assert state.synced_orders[1].status == 'blocked'
    assert state.synced_orders[1].blocked_reason == 'high_frequency_duplicate'


def test_process_tick_does_not_duplicate_blocked_record_for_same_ticket(monkeypatch):
    state = OrderSyncState(
        enabled=True,
        block_high_frequency_orders=True,
        high_frequency_window_seconds=5,
        credentials=[{
            'id': 'credential-1',
            'user_name': 'user',
            'api_key': 'key',
            'account_id': 100,
            'is_active': True,
        }],
        mappings=[{
            'id': 'mapping-1',
            'mt5_symbol': 'XAUUSD',
            'topstep_contract_id': 'CON.F.US.GC.TEST',
            'mt5_lots': 0.1,
            'topstep_contracts': 1,
            'is_active': True,
        }],
        synced_orders=[SyncedOrder(
            mt5_ticket=1,
            mt5_symbol='XAUUSD',
            mt5_volume=0.1,
            topstep_account_id=100,
            topstep_contract_id='CON.F.US.GC.TEST',
            side='buy',
            size=1,
            opened_at='2026-05-04T00:00:00+00:00',
        )],
    )
    fake_client = FakeTopStepClient()
    reset_order_sync_state_for_tests(state)
    monkeypatch.setattr(order_sync_service, '_utc_now', lambda: '2026-05-04T00:00:04+00:00')
    monkeypatch.setattr(order_sync_service, 'get_positions', lambda: [
        {'ticket': 1, 'symbol': 'XAUUSD', 'type': 0, 'volume': 0.1},
        {'ticket': 2, 'symbol': 'XAUUSD', 'type': 0, 'volume': 0.1},
    ])
    monkeypatch.setattr(order_sync_service, '_get_client', lambda credential_id: fake_client)
    monkeypatch.setattr(order_sync_service, '_save', lambda: None)

    asyncio.run(process_order_sync_tick())
    asyncio.run(process_order_sync_tick())

    blocked_orders = [order for order in state.synced_orders if order.status == 'blocked']
    assert fake_client.open_calls == 0
    assert len(blocked_orders) == 1
    assert blocked_orders[0].mt5_ticket == 2


def test_process_tick_retries_error_ticket_on_later_tick(monkeypatch):
    state = OrderSyncState(
        enabled=True,
        credentials=[{
            'id': 'credential-1',
            'user_name': 'user',
            'api_key': 'key',
            'account_id': 100,
            'is_active': True,
        }],
        mappings=[{
            'id': 'mapping-1',
            'mt5_symbol': 'XAUUSD',
            'topstep_contract_id': 'CON.F.US.GC.TEST',
            'mt5_lots': 0.1,
            'topstep_contracts': 1,
            'is_active': True,
        }],
        synced_orders=[SyncedOrder(
            mt5_ticket=1,
            mt5_symbol='XAUUSD',
            mt5_volume=0.1,
            topstep_account_id=100,
            topstep_contract_id='CON.F.US.GC.TEST',
            side='buy',
            size=1,
            status='error',
            opened_at='2026-05-04T00:00:00+00:00',
            last_error='temporary open failure',
        )],
    )
    fake_client = FakeTopStepClient()
    reset_order_sync_state_for_tests(state)
    monkeypatch.setattr(order_sync_service, 'get_positions', lambda: [{'ticket': 1, 'symbol': 'XAUUSD', 'type': 0, 'volume': 0.1}])
    monkeypatch.setattr(order_sync_service, '_get_client', lambda credential_id: fake_client)
    monkeypatch.setattr(order_sync_service, '_save', lambda: None)

    asyncio.run(process_order_sync_tick())

    assert fake_client.open_calls == 1
    assert len(state.synced_orders) == 2
    assert state.synced_orders[-1].status == 'open'
    assert state.synced_orders[-1].topstep_order_id == 9056


def test_order_sync_loop_propagates_cancellation(monkeypatch):
    calls = {'tick': 0}

    async def fake_process_order_sync_tick():
        calls['tick'] += 1

    async def fake_sleep(seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(order_sync_service, 'process_order_sync_tick', fake_process_order_sync_tick)
    monkeypatch.setattr(order_sync_service.asyncio, 'sleep', fake_sleep)
    monkeypatch.setattr(order_sync_service, '_save', lambda: None)

    try:
        asyncio.run(order_sync_service.order_sync_loop())
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError('order_sync_loop did not propagate cancellation')

    assert calls['tick'] == 1
