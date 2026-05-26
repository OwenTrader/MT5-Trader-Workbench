from python_service.app.services import mt5_service


class FakeMT5:
    def __init__(self, initialize_results, account_info_results=None):
        self.initialize_results = list(initialize_results)
        self.account_info_results = list(account_info_results or [])
        self.calls = []
        self.shutdown_calls = 0

    def initialize(self, **kwargs):
        self.calls.append(kwargs)
        if self.initialize_results:
            return self.initialize_results.pop(0)
        return False

    def shutdown(self):
        self.shutdown_calls += 1

    def last_error(self):
        return (1, 'failed')

    def account_info(self):
        if self.account_info_results:
            return self.account_info_results.pop(0)
        return object()

    def terminal_info(self):
        class TerminalInfo:
            def _asdict(self):
                return {}

        return TerminalInfo()


def test_init_mt5_without_launch_does_not_use_path(monkeypatch):
    fake_mt5 = FakeMT5([False])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)
    monkeypatch.setattr(mt5_service, 'list_running_mt5_paths', lambda: [])

    result = mt5_service.init_mt5('C:/MetaTrader 5/terminal64.exe', allow_launch=False)

    assert result is False
    assert fake_mt5.calls == []


def test_init_mt5_with_launch_uses_existing_directory_terminal(monkeypatch):
    fake_mt5 = FakeMT5([True], [object()])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)
    monkeypatch.setattr(mt5_service.os.path, 'exists', lambda path: True)
    monkeypatch.setattr(mt5_service.os.path, 'isdir', lambda path: path == 'C:/MetaTrader 5')
    monkeypatch.setattr(mt5_service.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(mt5_service, 'list_running_mt5_paths', lambda: ['C:/MetaTrader 5/terminal64.exe'])

    result = mt5_service.init_mt5('C:/MetaTrader 5', allow_launch=True)

    assert result is True
    assert fake_mt5.calls == [{'path': 'C:/MetaTrader 5/terminal64.exe'}]


def test_init_mt5_without_prefer_existing_uses_requested_terminal_first(monkeypatch):
    fake_mt5 = FakeMT5([True])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)
    monkeypatch.setattr(mt5_service.os.path, 'exists', lambda path: True)
    monkeypatch.setattr(mt5_service.os.path, 'isdir', lambda path: False)

    result = mt5_service.init_mt5('C:/MetaTrader 5/terminal64.exe', allow_launch=True, prefer_existing=False)

    assert result is True
    assert fake_mt5.calls == [{'path': 'C:/MetaTrader 5/terminal64.exe'}]


def test_init_mt5_tries_multiple_running_terminals_until_one_has_account(monkeypatch):
    fake_mt5 = FakeMT5([True, True], [None, object()])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)
    monkeypatch.setattr(mt5_service, 'list_running_mt5_paths', lambda: ['C:/MT5/A/terminal64.exe', 'C:/MT5/B/terminal64.exe'])

    result = mt5_service.init_mt5(allow_launch=False)

    assert result is True
    assert fake_mt5.calls == [
        {'path': 'C:/MT5/A/terminal64.exe'},
        {'path': 'C:/MT5/B/terminal64.exe'},
    ]


def test_init_mt5_returns_false_when_running_terminals_are_unusable_and_launch_disallowed(monkeypatch):
    fake_mt5 = FakeMT5([True, False], [None])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)
    monkeypatch.setattr(mt5_service, 'list_running_mt5_paths', lambda: ['C:/MT5/A/terminal64.exe', 'C:/MT5/B/terminal64.exe'])

    result = mt5_service.init_mt5(allow_launch=False)

    assert result is False
    assert fake_mt5.calls == [
        {'path': 'C:/MT5/A/terminal64.exe'},
        {'path': 'C:/MT5/B/terminal64.exe'},
    ]


def test_shutdown_mt5_suppresses_mt5_errors(monkeypatch):
    class BrokenMT5:
        def shutdown(self):
            raise RuntimeError('ipc already closed')

    monkeypatch.setattr(mt5_service, 'mt5', BrokenMT5())

    mt5_service.shutdown_mt5()


def test_verify_mt5_credentials_uses_terminal_login(monkeypatch):
    fake_mt5 = FakeMT5([True])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)
    monkeypatch.setattr(mt5_service.os.path, 'exists', lambda path: True)
    monkeypatch.setattr(mt5_service.os.path, 'isdir', lambda path: False)

    success, detail = mt5_service.verify_mt5_credentials('C:/MT5/terminal64.exe', '1001', 'secret', 'Demo-Server')

    assert success is True
    assert detail is None
    assert fake_mt5.calls == [{'path': 'C:/MT5/terminal64.exe', 'login': 1001, 'password': 'secret', 'server': 'Demo-Server'}]


def test_verify_mt5_credentials_rejects_non_numeric_login(monkeypatch):
    monkeypatch.setattr(mt5_service.os.path, 'exists', lambda path: True)
    monkeypatch.setattr(mt5_service.os.path, 'isdir', lambda path: False)

    success, detail = mt5_service.verify_mt5_credentials('C:/MT5/terminal64.exe', 'abc', 'secret', 'Demo-Server')

    assert success is False
    assert detail == 'MT5 login must be numeric'


def test_init_mt5_account_always_uses_requested_terminal_and_credentials(monkeypatch):
    fake_mt5 = FakeMT5([True])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)
    monkeypatch.setattr(mt5_service.os.path, 'exists', lambda path: True)
    monkeypatch.setattr(mt5_service.os.path, 'isdir', lambda path: False)

    success, detail = mt5_service.init_mt5_account('C:/MT5/terminal64.exe', '1001', 'secret', 'Demo-Server')

    assert success is True
    assert detail is None
    assert fake_mt5.shutdown_calls == 1
    assert fake_mt5.calls == [{'path': 'C:/MT5/terminal64.exe', 'login': 1001, 'password': 'secret', 'server': 'Demo-Server'}]


def test_verify_mt5_path_connection_uses_requested_terminal_and_shuts_down(monkeypatch):
    fake_mt5 = FakeMT5([True])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)
    monkeypatch.setattr(mt5_service.os.path, 'exists', lambda path: True)
    monkeypatch.setattr(mt5_service.os.path, 'isdir', lambda path: False)

    success, detail, terminal_info = mt5_service.verify_mt5_path_connection('C:/MT5/terminal64.exe')

    assert success is True
    assert detail is None
    assert terminal_info == {}
    assert fake_mt5.shutdown_calls == 2
    assert fake_mt5.calls == [{'path': 'C:/MT5/terminal64.exe'}]
