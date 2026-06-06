from python_service.app.local_copy_trading.models import Account, CopyRelationship, LocalCopyTradingState
from python_service.app.local_copy_trading.runtime import add_account, add_relationship, build_overview, remove_account, update_runtime_settings


def test_runtime_adds_relationship():
    state = LocalCopyTradingState()
    add_account(state, Account(id='src-1', name='Main A'))
    add_account(state, Account(id='fol-1', name='Follower A'))
    updated = add_relationship(
        state,
        CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'),
    )

    assert len(updated.relationships) == 1
    assert updated.relationships[0].id == 'rel-1'


def test_runtime_adds_accounts():
    state = LocalCopyTradingState()
    add_account(state, Account(id='src-1', name='Main A'))
    add_account(state, Account(id='fol-1', name='Follower A'))

    assert state.accounts[0].name == 'Main A'
    assert state.accounts[1].name == 'Follower A'


def test_runtime_builds_overview_payload():
    state = LocalCopyTradingState(enabled=True, poll_interval_seconds=2)
    add_account(state, Account(id='src-1', name='Main A'))

    overview = build_overview(state)

    assert overview['runtime']['enabled'] is True
    assert overview['runtime']['poll_interval_seconds'] == 2
    assert overview['accounts'][0]['id'] == 'src-1'


def test_runtime_updates_enabled_and_poll_interval():
    state = LocalCopyTradingState()

    update_runtime_settings(state, enabled=True, poll_interval_seconds=3)

    assert state.enabled is True
    assert state.poll_interval_seconds == 3


def test_runtime_removes_account_and_dependent_relationships():
    state = LocalCopyTradingState()
    add_account(state, Account(id='src-1', name='Main A'))
    add_account(state, Account(id='fol-1', name='Follower A'))
    add_relationship(
        state,
        CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'),
    )

    remove_account(state, 'src-1')

    assert state.accounts == [Account(id='fol-1', name='Follower A')]
    assert state.relationships == []
