from python_service.app.services import mt5_service


class FakeMT5:
    def __init__(self, initialize_results):
        self.initialize_results = list(initialize_results)
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
        return object()


def test_init_mt5_without_launch_does_not_use_path(monkeypatch):
    fake_mt5 = FakeMT5([False])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)

    result = mt5_service.init_mt5('C:/MetaTrader 5/terminal64.exe', allow_launch=False)

    assert result is False
    assert fake_mt5.calls == [{}]


def test_init_mt5_with_launch_uses_existing_directory_terminal(monkeypatch):
    fake_mt5 = FakeMT5([False, True])
    monkeypatch.setattr(mt5_service, 'mt5', fake_mt5)
    monkeypatch.setattr(mt5_service.os.path, 'exists', lambda path: True)
    monkeypatch.setattr(mt5_service.os.path, 'isdir', lambda path: path == 'C:/MetaTrader 5')
    monkeypatch.setattr(mt5_service.time, 'sleep', lambda seconds: None)

    result = mt5_service.init_mt5('C:/MetaTrader 5', allow_launch=True)

    assert result is True
    assert fake_mt5.calls == [{}, {'path': 'C:/MetaTrader 5/terminal64.exe'}]


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
