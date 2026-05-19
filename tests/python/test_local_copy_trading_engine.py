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
