from python_service.app.local_copy_trading.models import Account, LocalCopyTradingState
from python_service.app.local_copy_trading.storage import load_state, save_state


def test_storage_loads_default_state_when_file_missing(tmp_path):
    state = load_state(tmp_path / 'local_copy_trading.json')

    assert state.enabled is False
    assert state.accounts == []


def test_storage_loads_default_state_when_file_empty(tmp_path):
    path = tmp_path / 'local_copy_trading.json'
    path.write_text('', encoding='utf-8')

    state = load_state(path)

    assert state.enabled is False
    assert state.accounts == []


def test_storage_loads_state_with_utf8_bom(tmp_path):
    path = tmp_path / 'local_copy_trading.json'
    path.write_text('\ufeff{"enabled": true}', encoding='utf-8')

    state = load_state(path)

    assert state.enabled is True


def test_storage_saves_and_loads_state(tmp_path):
    path = tmp_path / 'local_copy_trading.json'
    initial = LocalCopyTradingState(accounts=[Account(id='src-1', name='Main A')])

    save_state(initial, path)
    loaded = load_state(path)

    assert loaded.accounts[0].id == 'src-1'
    assert loaded.accounts[0].name == 'Main A'


def test_storage_loads_legacy_source_and_follower_lists(tmp_path):
    path = tmp_path / 'local_copy_trading.json'
    path.write_text('{"source_accounts":[{"id":"src-1","name":"Main A"}],"follower_accounts":[{"id":"fol-1","name":"Follower A"}]}', encoding='utf-8')

    loaded = load_state(path)

    assert [account.id for account in loaded.accounts] == ['src-1', 'fol-1']
