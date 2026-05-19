from python_service.app.local_copy_trading.models import (
    CopyRelationship,
    FollowerAccount,
    LocalCopyTradingState,
    SourceAccount,
)


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
    assert state.relationships[0].symbol == 'XAUUSD'
    assert state.relationships[1].symbol == 'NAS100'
