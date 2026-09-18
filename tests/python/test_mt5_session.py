import pytest

from python_service.app.services import mt5_session


class FakeMt5:
    """Stand-in for the MetaTrader5 module object."""


@pytest.fixture(autouse=True)
def _reset_session():
    mt5_session.reset_session_tracking()
    yield
    mt5_session.reset_session_tracking()


def _fake_init(init_calls, result=(True, None)):
    def fake_init_mt5_account(terminal_path, login, password, server):
        init_calls.append((terminal_path, login, server))
        return result

    return fake_init_mt5_account


def test_use_account_initializes_once_for_a_new_account(monkeypatch):
    init_calls = []
    monkeypatch.setattr(mt5_session, 'mt5', FakeMt5())
    monkeypatch.setattr(mt5_session, 'init_mt5_account', _fake_init(init_calls))

    with mt5_session.use_account('D:/MT5/a/terminal64.exe', '1001', 'pw', 'Demo'):
        pass

    assert init_calls == [('D:/MT5/a/terminal64.exe', '1001', 'Demo')]
    assert mt5_session.get_current_key() is not None


def test_use_account_reuses_the_live_connection_for_the_same_account(monkeypatch):
    init_calls = []
    monkeypatch.setattr(mt5_session, 'mt5', FakeMt5())
    monkeypatch.setattr(mt5_session, 'init_mt5_account', _fake_init(init_calls))

    with mt5_session.use_account('D:/MT5/a/terminal64.exe', '1001', 'pw', 'Demo'):
        pass
    with mt5_session.use_account('D:/MT5/a/terminal64.exe', '1001', 'pw', 'Demo'):
        pass

    assert len(init_calls) == 1


def test_use_account_normalizes_path_and_server_case(monkeypatch):
    init_calls = []
    monkeypatch.setattr(mt5_session, 'mt5', FakeMt5())
    monkeypatch.setattr(mt5_session, 'init_mt5_account', _fake_init(init_calls))

    with mt5_session.use_account('D:/MT5/a/terminal64.exe', '1001', 'pw', 'Demo'):
        pass
    with mt5_session.use_account('D:\\MT5\\a\\terminal64.exe', '1001', 'pw', 'DEMO'):
        pass

    assert len(init_calls) == 1


def test_use_account_switches_when_the_account_changes(monkeypatch):
    init_calls = []
    monkeypatch.setattr(mt5_session, 'mt5', FakeMt5())
    monkeypatch.setattr(mt5_session, 'init_mt5_account', _fake_init(init_calls))

    with mt5_session.use_account('D:/MT5/a/terminal64.exe', '1001', 'pw', 'Demo'):
        pass
    with mt5_session.use_account('D:/MT5/b/terminal64.exe', '2002', 'pw', 'Demo'):
        pass

    assert len(init_calls) == 2


def test_use_account_yields_the_mt5_module(monkeypatch):
    client = FakeMt5()
    monkeypatch.setattr(mt5_session, 'mt5', client)
    monkeypatch.setattr(mt5_session, 'init_mt5_account', _fake_init([]))

    with mt5_session.use_account('D:/MT5/a/terminal64.exe', '1001', 'pw', 'Demo') as active:
        assert active is client


def test_use_account_raises_and_clears_key_when_connect_fails(monkeypatch):
    monkeypatch.setattr(mt5_session, 'mt5', FakeMt5())
    monkeypatch.setattr(mt5_session, 'init_mt5_account', _fake_init([], result=(False, 'bad credentials')))

    with pytest.raises(mt5_session.Mt5SessionError, match='bad credentials'):
        with mt5_session.use_account('D:/MT5/a/terminal64.exe', '1001', 'pw', 'Demo'):
            pass

    assert mt5_session.get_current_key() is None


def test_release_session_shuts_down_and_clears_key(monkeypatch):
    shutdown_calls = []
    monkeypatch.setattr(mt5_session, 'mt5', FakeMt5())
    monkeypatch.setattr(mt5_session, 'init_mt5_account', _fake_init([]))
    monkeypatch.setattr(mt5_session, 'shutdown_mt5', lambda: shutdown_calls.append(1))

    with mt5_session.use_account('D:/MT5/a/terminal64.exe', '1001', 'pw', 'Demo'):
        pass
    mt5_session.release_session()

    assert shutdown_calls == [1]
    assert mt5_session.get_current_key() is None
