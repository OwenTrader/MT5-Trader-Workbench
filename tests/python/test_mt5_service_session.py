"""The process-wide MT5 connection must not be switched behind mt5_session's back."""

from collections import namedtuple

import python_service.app.services.mt5_service as mt5_service
import python_service.app.services.mt5_session as mt5_session
from python_service.app.services.mt5_service import shutdown_mt5, verify_mt5_credentials


AccountInfo = namedtuple('AccountInfo', ['login', 'name'])


class FakeMt5:
    def __init__(self):
        self.initialized = False

    def shutdown(self):
        self.initialized = False

    def initialize(self, **kwargs):
        self.initialized = True
        return True

    def account_info(self):
        if not self.initialized:
            return None
        return AccountInfo(login=1001, name='Demo')

    def last_error(self):
        return (0, 'ok')


def _assume_session_connected(monkeypatch):
    monkeypatch.setattr(mt5_session, '_current_key', 'sentinel-account')
    assert mt5_session.get_current_key() == 'sentinel-account'


def test_shutdown_mt5_invalidates_the_tracked_session(monkeypatch):
    _assume_session_connected(monkeypatch)
    monkeypatch.setattr(mt5_service, 'mt5', FakeMt5())

    shutdown_mt5()

    assert mt5_session.get_current_key() is None


def test_verify_mt5_credentials_invalidates_the_tracked_session(monkeypatch, tmp_path):
    _assume_session_connected(monkeypatch)
    monkeypatch.setattr(mt5_service, 'mt5', FakeMt5())
    terminal = tmp_path / 'terminal64.exe'
    terminal.write_text('')
    monkeypatch.setattr(mt5_service, '_resolve_mt5_executable_path', lambda path: str(terminal))

    success, detail = verify_mt5_credentials(str(terminal), '1001', 'secret', 'Demo')

    assert success is True
    # verify ends with mt5.shutdown(): the tracked session must be forgotten,
    # otherwise copy trading would reuse a dead connection.
    assert mt5_session.get_current_key() is None
