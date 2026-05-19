from python_service.app.local_copy_trading.models import LocalCopyTradingState, SourceAccount
from python_service.app.local_copy_trading.storage import load_state, save_state


def test_storage_loads_default_state_when_file_missing(tmp_path):
    state = load_state(tmp_path / 'local_copy_trading.json')

    assert state.enabled is False
    assert state.source_accounts == []
    assert state.follower_accounts == []


def test_storage_saves_and_loads_state(tmp_path):
    path = tmp_path / 'local_copy_trading.json'
    initial = LocalCopyTradingState(source_accounts=[SourceAccount(id='src-1', name='Main A')])

    save_state(initial, path)
    loaded = load_state(path)

    assert loaded.source_accounts[0].id == 'src-1'
    assert loaded.source_accounts[0].name == 'Main A'
