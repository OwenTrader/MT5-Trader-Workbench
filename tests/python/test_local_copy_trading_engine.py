from python_service.app.local_copy_trading.engine import process_tick
from python_service.app.local_copy_trading.models import (
    CopyRelationship,
    FollowerAccount,
    LocalCopyTradingState,
    SourceAccount,
)


def test_engine_fans_out_one_source_position_to_multiple_followers():
    state = LocalCopyTradingState(
        enabled=True,
        source_accounts=[SourceAccount(id='src-1', name='Main A')],
        follower_accounts=[
            FollowerAccount(id='fol-1', name='Follower A'),
            FollowerAccount(id='fol-2', name='Follower B'),
        ],
        relationships=[
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'),
            CopyRelationship(id='rel-2', source_account_id='src-1', follower_account_id='fol-2', symbol='XAUUSD'),
        ],
    )

    events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])

    assert len(events) == 2
    assert len(state.events) == 2


def test_engine_filters_by_source_account_and_symbol():
    state = LocalCopyTradingState(
        follower_accounts=[FollowerAccount(id='fol-1', name='Follower A')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')],
    )

    events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-2', 'symbol': 'XAUUSD'}])

    assert events == []


def test_engine_skips_inactive_relationships_and_followers():
    state = LocalCopyTradingState(
        follower_accounts=[FollowerAccount(id='fol-1', name='Follower A', is_active=False)],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD', is_active=False)],
    )

    events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])

    assert events == []


def test_engine_deduplicates_already_copied_positions():
    state = LocalCopyTradingState(
        enabled=True,
        source_accounts=[SourceAccount(id='src-1', name='Main A')],
        follower_accounts=[FollowerAccount(id='fol-1', name='Follower A')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')],
    )

    first_events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])
    second_events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])

    assert len(first_events) == 1
    assert second_events == []


def test_engine_maps_source_symbol_to_follower_symbol():
    state = LocalCopyTradingState(
        enabled=True,
        source_accounts=[SourceAccount(id='src-1', name='Main A')],
        follower_accounts=[FollowerAccount(id='fol-1', name='Follower A')],
        relationships=[
            CopyRelationship(
                id='rel-1',
                source_account_id='src-1',
                follower_account_id='fol-1',
                symbol='XAUUSD',
                follower_symbol='XAUUSD.m',
            ),
        ],
    )

    events = process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])

    assert len(events) == 1
    assert events[0].symbol == 'XAUUSD.m'
    assert events[0].message == 'Mapped XAUUSD to XAUUSD.m'


def test_engine_records_follower_position_details_from_copy_executor():
    state = LocalCopyTradingState(
        enabled=True,
        follower_accounts=[FollowerAccount(id='fol-1', name='Follower A')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')],
    )

    events = process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}],
        execute_copy=lambda follower, relationship, position: (True, 'copied', 'fol-pos-1', 'fol-order-1'),
    )

    assert events[0].follower_position_id == 'fol-pos-1'
    assert events[0].follower_order_id == 'fol-order-1'


def test_engine_closes_copied_position_when_source_position_disappears():
    state = LocalCopyTradingState(
        enabled=True,
        follower_accounts=[FollowerAccount(id='fol-1', name='Follower A')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')],
    )
    process_tick(
        state,
        source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}],
        execute_copy=lambda follower, relationship, position: (True, 'copied', 'fol-pos-1', 'fol-order-1'),
    )

    events = process_tick(
        state,
        source_positions=[],
        execute_close=lambda follower, relationship, copied_event: (True, f'closed {copied_event.follower_position_id}'),
    )

    assert len(events) == 1
    assert events[0].status == 'closed'
    assert events[0].position_id == 'pos-1'
    assert events[0].follower_position_id == 'fol-pos-1'
    assert events[0].message == 'closed fol-pos-1'


def test_engine_does_not_close_same_copied_position_twice():
    state = LocalCopyTradingState(
        enabled=True,
        follower_accounts=[FollowerAccount(id='fol-1', name='Follower A')],
        relationships=[CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD')],
    )
    process_tick(state, source_positions=[{'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'}])
    first_close = process_tick(state, source_positions=[])
    second_close = process_tick(state, source_positions=[])

    assert len(first_close) == 1
    assert first_close[0].status == 'closed'
    assert second_close == []
