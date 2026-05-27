from python_service.app.local_copy_trading.models import (
    CopyRelationship,
    FollowerAccount,
    LocalCopyTradingState,
    SourceAccount,
)
import pytest


def test_local_copy_trading_state_supports_multiple_sources_and_followers():
    state = LocalCopyTradingState(
        source_accounts=[
            SourceAccount(id='src-1', name='Main A'),
            SourceAccount(id='src-2', name='Main B'),
        ],
        follower_accounts=[
            FollowerAccount(id='fol-1', name='Follower A'),
            FollowerAccount(id='fol-2', name='Follower B'),
        ],
        relationships=[
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='xauusd'),
            CopyRelationship(id='rel-2', source_account_id='src-2', follower_account_id='fol-2', symbol='nas100'),
        ],
    )

    assert len(state.source_accounts) == 2
    assert len(state.follower_accounts) == 2
    assert state.relationships[0].symbol == 'xauusd'
    assert state.relationships[1].symbol == 'nas100'


def test_copy_relationship_supports_different_follower_symbol_mapping():
    relationship = CopyRelationship(
        id='rel-1',
        source_account_id='src-1',
        follower_account_id='fol-1',
        symbol='xauusd',
        follower_symbol='xauusd.m',
    )

    assert relationship.symbol == 'xauusd'
    assert relationship.source_symbol == 'xauusd'
    assert relationship.follower_symbol == 'xauusd.m'


def test_copy_relationship_accepts_new_symbol_mapping_fields_without_legacy_symbol():
    relationship = CopyRelationship(
        id='rel-1',
        source_account_id='src-1',
        follower_account_id='fol-1',
        source_symbol='xauusd',
        follower_symbol='xauusd.m',
    )

    assert relationship.symbol == 'xauusd'
    assert relationship.source_symbol == 'xauusd'
    assert relationship.follower_symbol == 'xauusd.m'


def test_copy_relationship_rejects_non_positive_lot_multiplier():
    with pytest.raises(ValueError, match='lot_multiplier must be greater than 0'):
        CopyRelationship(
            id='rel-1',
            source_account_id='src-1',
            follower_account_id='fol-1',
            source_symbol='XAUUSD',
            follower_symbol='XAUUSD.m',
            lot_multiplier=0,
        )
