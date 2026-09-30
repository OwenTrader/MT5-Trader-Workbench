from collections import namedtuple
from contextlib import contextmanager

import pytest

from python_service.app.local_copy_trading import source_adapter
from python_service.app.local_copy_trading.models import Account, CopyRelationship, LocalCopyTradingState
from python_service.app.services.mt5_session import Mt5SessionError


Position = namedtuple('Position', ['ticket', 'symbol', 'type', 'volume'])


class FakeClient:
    def positions_get(self):
        return [Position(ticket=123, symbol='XAUUSD.m', type=0, volume=0.2)]


def _source_state(**account_overrides):
    account_fields = {
        'id': 'src-1',
        'name': 'Main A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'C:/MT5/source/terminal64.exe',
        'login': '1001',
        'password': 'secret',
        'server': 'Demo',
    }
    account_fields.update(account_overrides)
    return LocalCopyTradingState(
        accounts=[Account(**account_fields)],
        relationships=[
            CopyRelationship(
                id='rel-1',
                source_account_id='src-1',
                follower_account_id='fol-1',
                symbol='XAUUSD',
            )
        ],
    )


def test_source_adapter_reads_positions_through_the_shared_session(monkeypatch):
    state = _source_state()
    sessions = []

    @contextmanager
    def fake_use_account(terminal_path, login, password, server):
        sessions.append((terminal_path, login, server))
        yield FakeClient()

    monkeypatch.setattr(source_adapter, 'use_account', fake_use_account)

    positions = source_adapter.get_source_positions(state)

    assert positions == [
        {
            'ticket': 123,
            'symbol': 'XAUUSD.m',
            'type': 0,
            'volume': 0.2,
            'source_account_id': 'src-1',
            'position_id': '123',
        },
    ]
    assert sessions == [('C:/MT5/source/terminal64.exe', '1001', 'Demo')]


def test_source_adapter_reads_each_source_account_once_per_call(monkeypatch):
    state = LocalCopyTradingState(
        accounts=[
            Account(
                id='src-1',
                name='Main A',
                connection_type='mt5_terminal',
                terminal_path='C:/MT5/a/terminal64.exe',
                login='1001',
                password='secret',
                server='Demo',
            ),
            Account(
                id='src-2',
                name='Main B',
                connection_type='mt5_terminal',
                terminal_path='C:/MT5/b/terminal64.exe',
                login='2002',
                password='secret',
                server='Demo',
            ),
        ],
        relationships=[
            CopyRelationship(
                id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'
            ),
            CopyRelationship(
                id='rel-2', source_account_id='src-2', follower_account_id='fol-1', symbol='XAUUSD'
            ),
        ],
    )
    sessions = []

    @contextmanager
    def fake_use_account(terminal_path, login, password, server):
        sessions.append(login)
        yield FakeClient()

    monkeypatch.setattr(source_adapter, 'use_account', fake_use_account)

    source_adapter.get_source_positions(state)

    assert sessions == ['1001', '2002']


def test_source_adapter_reports_source_connection_failure(monkeypatch):
    state = _source_state()

    def fake_use_account(*args, **kwargs):
        raise Mt5SessionError('source login failed')

    monkeypatch.setattr(source_adapter, 'use_account', fake_use_account)

    with pytest.raises(RuntimeError, match='source login failed'):
        source_adapter.get_source_positions(state)


def test_source_adapter_keeps_healthy_accounts_when_one_terminal_is_unreachable(monkeypatch):
    """One dead terminal must not stop the other accounts from being copied."""
    state = LocalCopyTradingState(
        accounts=[
            Account(
                id='src-1',
                name='Main A',
                connection_type='mt5_terminal',
                terminal_path='C:/MT5/a/terminal64.exe',
                login='1001',
                password='secret',
                server='Demo',
            ),
            Account(
                id='src-2',
                name='Main B',
                connection_type='mt5_terminal',
                terminal_path='C:/MT5/b/terminal64.exe',
                login='2002',
                password='secret',
                server='Demo',
            ),
        ],
        relationships=[
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'),
            CopyRelationship(id='rel-2', source_account_id='src-2', follower_account_id='fol-1', symbol='XAUUSD'),
        ],
    )

    @contextmanager
    def fake_use_account(terminal_path, login, password, server):
        if login == '1001':
            raise Mt5SessionError('terminal a offline')
        yield FakeClient()

    monkeypatch.setattr(source_adapter, 'use_account', fake_use_account)

    positions = source_adapter.get_source_positions(state)

    assert [position['source_account_id'] for position in positions] == ['src-2']


def test_source_adapter_raises_when_every_terminal_is_unreachable(monkeypatch):
    state = LocalCopyTradingState(
        accounts=[
            Account(
                id='src-1',
                name='Main A',
                connection_type='mt5_terminal',
                terminal_path='C:/MT5/a/terminal64.exe',
                login='1001',
                password='secret',
                server='Demo',
            ),
            Account(
                id='src-2',
                name='Main B',
                connection_type='mt5_terminal',
                terminal_path='C:/MT5/b/terminal64.exe',
                login='2002',
                password='secret',
                server='Demo',
            ),
        ],
        relationships=[
            CopyRelationship(id='rel-1', source_account_id='src-1', follower_account_id='fol-1', symbol='XAUUSD'),
            CopyRelationship(id='rel-2', source_account_id='src-2', follower_account_id='fol-1', symbol='XAUUSD'),
        ],
    )

    @contextmanager
    def fake_use_account(terminal_path, login, password, server):
        raise Mt5SessionError(f'terminal {login} offline')

    monkeypatch.setattr(source_adapter, 'use_account', fake_use_account)

    with pytest.raises(RuntimeError, match='src-1: terminal 1001 offline; src-2: terminal 2002 offline'):
        source_adapter.get_source_positions(state)
