from python_service.app.local_copy_trading.models import (
    CopyRelationship,
    FollowerAccount,
    LocalCopyTradingState,
    SourceAccount,
)
from python_service.app.local_copy_trading.runtime import (
    add_follower_account,
    add_relationship,
    add_source_account,
    build_overview,
    remove_source_account,
    update_runtime_settings,
)


def test_runtime_adds_relationship():
    state = LocalCopyTradingState()
    add_source_account(state, SourceAccount(id='src-1', name='Main A'))
    add_follower_account(state, FollowerAccount(id='fol-1', name='Follower A'))
    updated = add_relationship(
        state,
        CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'),
    )

    assert len(updated.relationships) == 1
    assert updated.relationships[0].id == 'rel-1'


def test_runtime_adds_source_and_follower_accounts():
    state = LocalCopyTradingState()
    add_source_account(state, SourceAccount(id='src-1', name='Main A'))
    add_follower_account(state, FollowerAccount(id='fol-1', name='Follower A'))

    assert state.source_accounts[0].name == 'Main A'
    assert state.follower_accounts[0].name == 'Follower A'


def test_runtime_builds_overview_payload():
    state = LocalCopyTradingState(enabled=True, poll_interval_seconds=2)
    add_source_account(state, SourceAccount(id='src-1', name='Main A'))

    overview = build_overview(state)

    assert overview['runtime']['enabled'] is True
    assert overview['runtime']['poll_interval_seconds'] == 2
    assert overview['source_accounts'][0]['id'] == 'src-1'


def test_runtime_updates_enabled_and_poll_interval():
    state = LocalCopyTradingState()

    update_runtime_settings(state, enabled=True, poll_interval_seconds=3)

    assert state.enabled is True
    assert state.poll_interval_seconds == 3


def test_runtime_removes_source_account_and_dependent_relationships():
    state = LocalCopyTradingState()
    add_source_account(state, SourceAccount(id='src-1', name='Main A'))
    add_follower_account(state, FollowerAccount(id='fol-1', name='Follower A'))
    add_relationship(
        state,
        CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'),
    )

    remove_source_account(state, 'src-1')

    assert state.source_accounts == []
    assert state.relationships == []
