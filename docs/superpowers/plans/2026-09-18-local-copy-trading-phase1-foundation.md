# Local Copy Trading Phase 1 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local copy trading correct under real-money conditions: stop per-action MT5 reconnects, resolve follower positions by explicit ownership instead of symbol fallback, and make copy actions idempotent across process crashes.

**Architecture:** Add a process-wide account session layer (`services/mt5_session.py`) that keeps one MT5 connection alive per account and reuses it across ticks; make `engine.process_tick` schedule its work grouped by follower account so a single connection serves a whole batch; tag every follower order with `magic=260526` plus a deterministic `lc:<rel>:<pos>` comment so closes resolve ownership exactly instead of guessing; persist the order map and sync events in SQLite through a new `copy_service.py` two-phase write (`pending` → `confirmed`); reconcile local records against live follower positions on every tick so a crash mid-order cannot duplicate or orphan positions.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, `sqlite3`, MetaTrader5 Python API, pytest.

---

## Scope Check

This is one subsystem hardening effort. All ten tasks ship together and none of them is independently useful in production:

- Tasks 1–4 change where MT5 connections come from. Shipping only some of them leaves two competing connection owners, which is worse than today because MT5 allows exactly one connection per process.
- Tasks 5–8 build the persistence and reconciliation layer. Tasks 7 and 8 are meaningless without 5, and task 6 is meaningless without 5 because ownership tokens must be persisted to survive a restart.
- Task 9 and 10 are cheap and depend on the above.

Do not split this plan. Phase 2 (risk guard, volume modes, SL/TP sync, partial closes) is a separate plan and must not start until this one is merged.

## Design Decisions

**1. MT5 connection management must be process-global, not package-local.**

The MetaTrader5 Python package is a single-connection-per-process API: `mt5.initialize()` tears down whatever connection is currently open. This is visible in `python_service/app/services/mt5_service.py:252-263`, where `_init_mt5_account_unlocked` calls `mt5.shutdown()` before every `initialize`.

Two consequences follow directly:

- A connection layer *cannot* be duplicated per feature package. If `local_copy_trading` opened its own connection, it would silently disconnect the market-data polling loop and vice versa. They must share one owner.
- Therefore the session layer belongs under `python_service/app/services/`, next to the existing MT5 service, and `local_copy_trading` depends on it.

**Design Rule Amendment.** The plan `docs/superpowers/plans/2026-05-11-local-copy-trading-independent-backend.md` states in its Design Rule 2 that the `local_copy_trading` package must not import anything from `python_service.app.services.mt5*`. That rule is already violated by the current code: `local_copy_trading/follower_executor.py:5` and `local_copy_trading/source_adapter.py:2` both import from `services.mt5_service`. The rule as written is not achievable given the single-connection constraint above.

This plan amends the rule to:

> `local_copy_trading` **may** depend on `python_service.app.services.mt5_session` (connection lifecycle only) and `python_service.app.services.mt5_service` (primitives required to talk to MT5). It **must not** depend on `python_service.app.routes.mt5`, `python_service.app.services.order_sync*`, or `python_service.app.models.order_sync*`. Business logic for copy trading stays inside `local_copy_trading`.

**2. Ownership is recorded at order time, not inferred at close time.**

The MT5 `order` ticket returned by `order_send` is a *deal* identifier, not a *position* ticket. The current code conflates them (`follower_executor.py:94-111`) and falls back to "first position with the same symbol" when the lookup misses. Any account holding a manual position or another EA's position in the same symbol can therefore have the wrong position closed. The fix is to write an explicit ownership token into the order comment at open time and resolve closes by scanning for that token — never by symbol.

**3. Idempotency is enforced by a database unique constraint, not by in-memory state.**

Today `has_copied_position` (`engine.py:79-86`) reads an in-memory event list that is only persisted on the next `save_state` (`loop.py:24`). A crash between `order_send` and `save_state` loses the record and the next tick opens a second position. A `UNIQUE` constraint on `client_key` makes the duplicate impossible regardless of crash timing.

**4. Existing tests that assert the old connection behaviour must be updated, not preserved.**

Two existing test files encode the old per-action connect/disconnect contract and will fail after tasks 2 and 3:

- `tests/python/test_local_copy_trading_source_adapter.py:47` asserts `calls['shutdown'] == 1`.
- `tests/python/test_local_copy_trading_follower_executor.py:48-49` monkeypatches `init_mt5_account` and `shutdown_mt5` on the executor module.

This is an intended, documented behaviour change. Tasks 2 and 3 include the required test updates as explicit steps. Do not "fix" the failure by keeping a redundant `shutdown` call.

## File Structure

### New files

| Path | Responsibility |
| :--- | :--- |
| `python_service/app/services/mt5_session.py` | Own the single live MT5 account connection. Provide `use_account()` (reuse-or-switch), `release_session()`, and the account key derivation. No trading logic. |
| `python_service/app/local_copy_trading/copy_trading_db.py` | SQLite schema and CRUD for `copy_order_map`. Only persistence, no MT5 access. |
| `python_service/app/local_copy_trading/position_ownership.py` | Deterministic comment token generation and exact ownership matching. Pure functions, no I/O. |
| `python_service/app/local_copy_trading/copy_service.py` | Orchestrate a single copy/close action: idempotency lookup, two-phase write, delegate to `follower_executor`. Depends on db + executor, not on MT5 directly. |
| `python_service/app/local_copy_trading/reconcile.py` | Compare local order map against live follower positions and repair `pending`/`confirmed`/`drifted`/`orphan` states. |
| `tests/python/test_mt5_session.py` | Session reuse, switching, failure, release. |
| `tests/python/test_copy_trading_db.py` | Schema, unique constraint, status transitions. |
| `tests/python/test_local_copy_trading_ownership.py` | Token determinism, comment length, exact matching. |
| `tests/python/test_local_copy_trading_copy_service.py` | Two-phase write, duplicate suppression, failure marking. |
| `tests/python/test_local_copy_trading_reconcile.py` | Pending repair, drift detection, orphan reporting. |
| `tests/python/test_local_copy_trading_snapshot.py` | Source snapshot signature stability. |

### Existing files to modify

| Path | Change |
| :--- | :--- |
| `python_service/app/local_copy_trading/source_adapter.py` | Read positions through `use_account` instead of local `init`/`shutdown`. Add `positions_signature`. |
| `python_service/app/local_copy_trading/follower_executor.py` | Accept a live MT5 client instead of opening its own connection. Use ownership tokens. |
| `python_service/app/local_copy_trading/engine.py` | Schedule copy and close work grouped by follower account. |
| `python_service/app/local_copy_trading/loop.py` | Inject `copy_service` handlers, run reconciliation, skip ticks whose source snapshot is unchanged. |
| `python_service/app/main.py` | Release the shared session during lifespan shutdown. |
| `tests/python/test_local_copy_trading_source_adapter.py` | Replace shutdown assertions with session assertions. |
| `tests/python/test_local_copy_trading_follower_executor.py` | Inject a fake client instead of monkeypatching `init_mt5_account`. |

---

## Running the tests

All commands run from the repository root. The repo's `python_service/requirements.txt` includes `pytest`.

Use `python -m pytest` so the interpreter is explicit. Run only the file under test during TDD; run the whole copy-trading suite plus the route suite before the final commit of each task.

```bash
python -m pytest tests/python/test_mt5_session.py -v
python -m pytest tests/python -q -k "local_copy or copy_trading or mt5_session"
```

---

### Task 1: MT5 account session layer

**Files:**
- Create: `python_service/app/services/mt5_session.py`
- Test: `tests/python/test_mt5_session.py`

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_mt5_session.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_mt5_session.py -v`

Expected: collection error, `ModuleNotFoundError: No module named 'python_service.app.services.mt5_session'`

- [ ] **Step 3: Write the implementation**

Create `python_service/app/services/mt5_session.py`:

```python
"""Process-wide MT5 account session management.

The MetaTrader5 Python package allows exactly one live connection per process:
calling ``initialize`` discards whatever connection is currently open. Every
feature that talks to MT5 therefore has to share a single connection owner.

This module is that owner for account-scoped connections. It keeps the current
account key so that repeated work against the same account does not pay the
reconnect cost, and it deliberately does *not* shut the connection down when a
caller is done -- the next caller may be for the same account.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from python_service.app.services.mt5_service import (
    init_mt5_account,
    mt5,
    mt5_connection_lock,
    shutdown_mt5,
)


class Mt5SessionError(RuntimeError):
    """Raised when an account-scoped MT5 session cannot be established."""


_current_key: str | None = None


def account_key(terminal_path: str, login: str, server: str) -> str:
    """Build the identity of a connection target.

    Path separators and case are normalized so that the same terminal written
    two different ways is recognized as one account.
    """
    raw_path = str(terminal_path or '').strip()
    normalized_path = os.path.normcase(os.path.normpath(raw_path)) if raw_path else ''
    return '|'.join(
        (
            normalized_path,
            str(login or '').strip(),
            str(server or '').strip().casefold(),
        )
    )


def get_current_key() -> str | None:
    """Return the account key of the live connection, if any."""
    return _current_key


def reset_session_tracking() -> None:
    """Forget which account is connected without touching the connection.

    Intended for tests and for shutdown paths that close the connection
    themselves.
    """
    global _current_key
    _current_key = None


@contextmanager
def use_account(
    terminal_path: str,
    login: str,
    password: str,
    server: str,
) -> Iterator[object]:
    """Yield a live MT5 client bound to the given account.

    If the live connection already targets this account it is reused as-is.
    Otherwise the connection is switched, which costs a reconnect.

    Raises:
        Mt5SessionError: if the connection cannot be established.
    """
    global _current_key
    key = account_key(terminal_path, login, server)

    with mt5_connection_lock():
        if _current_key != key:
            success, detail = init_mt5_account(terminal_path, login, password, server)
            if not success:
                _current_key = None
                raise Mt5SessionError(detail or f'Failed to connect MT5 account {login}')
            _current_key = key
        yield mt5


def release_session() -> None:
    """Close the live connection and forget it. Call on application shutdown."""
    global _current_key
    with mt5_connection_lock():
        shutdown_mt5()
        _current_key = None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/python/test_mt5_session.py -v`

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add python_service/app/services/mt5_session.py tests/python/test_mt5_session.py
git commit -m "feat(copy-trading): add process-wide MT5 account session layer"
```

---

### Task 2: Read source positions through the shared session

**Files:**
- Modify: `python_service/app/local_copy_trading/source_adapter.py`
- Test: `tests/python/test_local_copy_trading_source_adapter.py`

The current adapter opens and closes its own connection for every source account. Replace that with `use_account`, which keeps the connection alive for the next caller.

- [ ] **Step 1: Update the test to describe the new contract**

Replace the whole of `tests/python/test_local_copy_trading_source_adapter.py` with:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_local_copy_trading_source_adapter.py -v`

Expected: FAIL. The first test errors because `source_adapter.use_account` does not exist yet; `_source_state` and the session assertions fail against the current `init_mt5_account`/`shutdown_mt5` implementation.

- [ ] **Step 3: Rewrite the adapter**

Replace the whole of `python_service/app/local_copy_trading/source_adapter.py` with:

```python
"""Acquire source-account positions through the shared MT5 session."""

from python_service.app.local_copy_trading.models import LocalCopyTradingState
from python_service.app.services.mt5_session import Mt5SessionError, use_account


def _as_dict(value) -> dict:
    if hasattr(value, '_asdict'):
        return value._asdict()
    if isinstance(value, dict):
        return value
    return dict(value)


def get_source_positions(state: LocalCopyTradingState) -> list[dict]:
    """Return every open position held by an active source account.

    Each MT5-backed account is visited once. The connection is left open for
    the next caller, so consecutive work on the same account is free.
    """
    positions: list[dict] = []
    source_account_ids = {
        relationship.source_account_id
        for relationship in state.relationships
        if relationship.is_active
    }

    for account in state.accounts:
        if account.id not in source_account_ids:
            continue
        if not account.is_active:
            continue
        if account.connection_type == 'simulated':
            positions.append({
                'position_id': f'{account.id}-sample-position',
                'source_account_id': account.id,
                'symbol': 'XAUUSD',
            })
            continue
        if account.connection_type != 'mt5_terminal':
            continue

        try:
            with use_account(
                account.terminal_path,
                account.login,
                account.password,
                account.server,
            ) as client:
                for position in client.positions_get() or []:
                    payload = _as_dict(position)
                    payload['source_account_id'] = account.id
                    payload['position_id'] = str(payload.get('ticket') or payload.get('identifier') or '')
                    positions.append(payload)
        except Mt5SessionError as error:
            raise RuntimeError(str(error)) from error

    return positions
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/python/test_local_copy_trading_source_adapter.py -v`

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/source_adapter.py tests/python/test_local_copy_trading_source_adapter.py
git commit -m "refactor(copy-trading): read source positions via shared session"
```

---

### Task 3: Execute follower orders through the shared session

**Files:**
- Modify: `python_service/app/local_copy_trading/follower_executor.py`
- Test: `tests/python/test_local_copy_trading_follower_executor.py`

The executor currently opens and closes a connection per order. Change it to accept a live client, so the caller decides the session lifetime. This task keeps the existing (unsafe) position lookup so the change stays reviewable; Task 6 replaces the lookup.

- [ ] **Step 1: Rewrite the test file against the new contract**

Replace the whole of `tests/python/test_local_copy_trading_follower_executor.py` with:

```python
from collections import namedtuple

import pytest

from python_service.app.local_copy_trading import follower_executor
from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount


Tick = namedtuple('Tick', ['ask', 'bid'])
SymbolInfo = namedtuple('SymbolInfo', ['volume_min', 'volume_step'])
OrderResult = namedtuple('OrderResult', ['retcode', 'order', 'deal', 'comment'])
Position = namedtuple('Position', ['ticket', 'identifier', 'symbol', 'type', 'volume'])


def _follower(**overrides):
    fields = {
        'id': 'fol-1',
        'name': 'Follower A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'D:/MT5/follower/terminal64.exe',
        'login': '2001',
        'password': 'secret',
        'server': 'Demo',
    }
    fields.update(overrides)
    return FollowerAccount(**fields)


def _relationship(**overrides):
    fields = {
        'id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'symbol': 'XAUUSD',
        'source_symbol': 'XAUUSD',
        'follower_symbol': 'XAUUSD.m',
    }
    fields.update(overrides)
    return CopyRelationship(**fields)


class FakeClient:
    POSITION_TYPE_BUY = 0
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008

    def __init__(self, positions=None):
        self.sent_requests = []
        self._positions = positions if positions is not None else []

    def symbol_select(self, symbol, enabled):
        return enabled is True

    def symbol_info(self, symbol):
        return SymbolInfo(volume_min=0.01, volume_step=0.01)

    def symbol_info_tick(self, symbol):
        return Tick(ask=2301.5, bid=2301.3)

    def order_send(self, request):
        self.sent_requests.append(request)
        return OrderResult(retcode=10009, order=456, deal=0, comment='done')

    def positions_get(self, symbol=None):
        return self._positions

    def last_error(self):
        return (0, 'ok')


def test_copy_position_opens_a_market_order_with_lot_multiplier():
    client = FakeClient()

    success, message, follower_position_id, follower_order_id = follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(lot_multiplier=2),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is True
    assert follower_order_id == '456'
    assert len(client.sent_requests) == 1
    request = client.sent_requests[0]
    assert request['symbol'] == 'XAUUSD.m'
    assert request['volume'] == 0.2
    assert request['type'] == FakeClient.ORDER_TYPE_BUY


def test_copy_position_reports_symbol_selection_failure():
    class FailingClient(FakeClient):
        def symbol_select(self, symbol, enabled):
            return False

    success, message, _, _ = follower_executor.copy_position_to_follower(
        FailingClient(),
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is False
    assert 'Failed to select follower symbol' in message


def test_copy_position_runs_without_a_follower_connection_for_simulated_accounts():
    success, message, follower_position_id, _ = follower_executor.copy_position_to_follower(
        None,
        _follower(connection_type='simulated'),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is True
    assert follower_position_id == 'pos-1'
    assert 'Simulated copy' in message


def test_copy_position_rejects_unsupported_connection_types():
    success, message, _, _ = follower_executor.copy_position_to_follower(
        None,
        _follower(connection_type='mt5_api'),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is False
    assert 'Unsupported follower connection type' in message


def test_close_position_uses_the_recorded_position_ticket():
    client = FakeClient(positions=[Position(ticket=789, identifier=456, symbol='XAUUSD.m', type=0, volume=0.2)])
    copied_event = follower_executor.SyncEvent(
        relationship_id='rel-1',
        source_account_id='src-1',
        follower_account_id='fol-1',
        position_id='pos-1',
        follower_position_id='789',
        follower_order_id='456',
        symbol='XAUUSD.m',
        status='copied',
        created_at='2026-09-18T00:00:00+00:00',
    )

    success, message = follower_executor.close_copied_position_on_follower(
        client,
        _follower(),
        _relationship(),
        copied_event,
    )

    assert success is True
    assert len(client.sent_requests) == 1
    request = client.sent_requests[0]
    assert request['position'] == 789
    assert request['type'] == FakeClient.ORDER_TYPE_SELL
    assert request['volume'] == 0.2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_local_copy_trading_follower_executor.py -v`

Expected: FAIL with `TypeError` — `copy_position_to_follower()` currently takes `(follower, relationship, source_position)` and does not accept a client.

- [ ] **Step 3: Rewrite the executor**

Replace the whole of `python_service/app/local_copy_trading/follower_executor.py` with:

```python
"""Execute follower-side MT5 orders against an already-open session.

The caller owns the connection (see ``services.mt5_session``). This module only
builds and validates order requests, so it can be tested without a terminal.
"""

import math

from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount, SyncEvent


def _position_is_buy(position: dict, client) -> bool:
    value = position.get('type')
    if isinstance(value, str):
        return value.strip().casefold() in {'buy', 'long', '0'}
    return int(value or 0) == getattr(client, 'POSITION_TYPE_BUY', 0)


def _normalize_volume(raw_volume: float, symbol_info) -> float:
    if raw_volume <= 0:
        raise ValueError('copy volume must be greater than 0')
    volume_min = float(getattr(symbol_info, 'volume_min', 0.01) or 0.01)
    volume_step = float(getattr(symbol_info, 'volume_step', 0.01) or 0.01)
    volume = max(raw_volume, volume_min)
    steps = math.floor((volume - volume_min) / volume_step + 0.000001)
    normalized = volume_min + steps * volume_step
    return round(max(normalized, volume_min), 8)


def _done_codes(client) -> set:
    return {
        getattr(client, 'TRADE_RETCODE_DONE', 10009),
        getattr(client, 'TRADE_RETCODE_PLACED', 10008),
    }


def copy_position_to_follower(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
) -> tuple[bool, str, str, str]:
    """Open a follower position mirroring ``source_position``.

    Returns ``(success, message, follower_position_id, follower_order_id)``.
    """
    if follower.connection_type == 'simulated':
        return True, f'Simulated copy {relationship.source_symbol} to {relationship.follower_symbol}', source_position.get('position_id', ''), ''
    if follower.connection_type != 'mt5_terminal':
        return False, f'Unsupported follower connection type: {follower.connection_type}', '', ''

    symbol = relationship.follower_symbol
    if not client.symbol_select(symbol, True):
        return False, f'Failed to select follower symbol {symbol}. Error: {client.last_error()}', '', ''

    symbol_info = client.symbol_info(symbol)
    tick = client.symbol_info_tick(symbol)
    if symbol_info is None or tick is None:
        return False, f'Missing tick or symbol info for follower symbol {symbol}. Error: {client.last_error()}', '', ''

    is_buy = _position_is_buy(source_position, client)
    order_type = getattr(client, 'ORDER_TYPE_BUY', 0) if is_buy else getattr(client, 'ORDER_TYPE_SELL', 1)
    price = float(getattr(tick, 'ask', 0) if is_buy else getattr(tick, 'bid', 0))
    if price <= 0:
        return False, f'Missing executable price for follower symbol {symbol}', '', ''

    source_volume = float(source_position.get('volume') or 0)
    try:
        volume = _normalize_volume(source_volume * relationship.lot_multiplier, symbol_info)
    except ValueError as error:
        return False, str(error), '', ''

    request = {
        'action': getattr(client, 'TRADE_ACTION_DEAL', 1),
        'symbol': symbol,
        'volume': volume,
        'type': order_type,
        'price': price,
        'deviation': 20,
        'magic': 260526,
        'comment': f'local-copy:{relationship.id[:16]}',
        'type_time': getattr(client, 'ORDER_TIME_GTC', 0),
        'type_filling': getattr(client, 'ORDER_FILLING_IOC', 1),
    }
    result = client.order_send(request)
    if result is None:
        return False, f'MT5 order_send returned no result. Error: {client.last_error()}', '', ''

    result_code = getattr(result, 'retcode', None)
    if result_code not in _done_codes(client):
        comment = getattr(result, 'comment', '')
        return False, f'MT5 order_send failed. Retcode: {result_code}. {comment}', '', ''

    order_id = getattr(result, 'order', '') or getattr(result, 'deal', '')
    follower_position_id = _find_follower_position_id(client, symbol, order_id)
    return True, f'Copied {relationship.source_symbol} to {symbol}, volume {volume}, order {order_id}', follower_position_id, str(order_id or '')


def _find_follower_position_id(client, symbol: str, order_id) -> str:
    """Best-effort match of an order ticket to a position ticket.

    Superseded by explicit ownership matching in Task 6; retained here so this
    task stays a pure connection change.
    """
    try:
        positions = client.positions_get(symbol=symbol) or client.positions_get() or []
    except TypeError:
        positions = client.positions_get() or []
    except Exception:
        return ''

    order_text = str(order_id or '')
    for position in positions:
        payload = position._asdict() if hasattr(position, '_asdict') else dict(position)
        if str(payload.get('ticket') or '') == order_text:
            return str(payload.get('ticket') or '')
        if str(payload.get('identifier') or '') == order_text:
            return str(payload.get('ticket') or payload.get('identifier') or '')
        if str(payload.get('symbol') or '').casefold() == symbol.casefold():
            return str(payload.get('ticket') or payload.get('identifier') or '')
    return ''


def close_copied_position_on_follower(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    copied_event: SyncEvent,
) -> tuple[bool, str]:
    """Close the follower position recorded on ``copied_event``."""
    if follower.connection_type == 'simulated':
        return True, f'Simulated close {copied_event.follower_position_id or copied_event.position_id}'
    if follower.connection_type != 'mt5_terminal':
        return False, f'Unsupported follower connection type: {follower.connection_type}'

    target_position = _find_position_to_close(client, copied_event)
    if target_position is None:
        return True, f'Follower position already closed for source position {copied_event.position_id}'

    symbol = str(target_position.get('symbol') or copied_event.symbol or relationship.follower_symbol)
    if not client.symbol_select(symbol, True):
        return False, f'Failed to select follower symbol {symbol}. Error: {client.last_error()}'

    tick = client.symbol_info_tick(symbol)
    if tick is None:
        return False, f'Missing tick for follower symbol {symbol}. Error: {client.last_error()}'

    is_buy = _position_is_buy(target_position, client)
    order_type = getattr(client, 'ORDER_TYPE_SELL', 1) if is_buy else getattr(client, 'ORDER_TYPE_BUY', 0)
    price = float(getattr(tick, 'bid', 0) if is_buy else getattr(tick, 'ask', 0))
    if price <= 0:
        return False, f'Missing close price for follower symbol {symbol}'

    position_ticket = int(target_position.get('ticket') or target_position.get('identifier') or 0)
    volume = float(target_position.get('volume') or 0)
    if position_ticket <= 0 or volume <= 0:
        return False, f'Invalid follower position data for {symbol}'

    request = {
        'action': getattr(client, 'TRADE_ACTION_DEAL', 1),
        'symbol': symbol,
        'volume': volume,
        'type': order_type,
        'position': position_ticket,
        'price': price,
        'deviation': 20,
        'magic': 260526,
        'comment': f'local-close:{relationship.id[:15]}',
        'type_time': getattr(client, 'ORDER_TIME_GTC', 0),
        'type_filling': getattr(client, 'ORDER_FILLING_IOC', 1),
    }
    result = client.order_send(request)
    if result is None:
        return False, f'MT5 close order_send returned no result. Error: {client.last_error()}'

    result_code = getattr(result, 'retcode', None)
    if result_code not in _done_codes(client):
        comment = getattr(result, 'comment', '')
        return False, f'MT5 close order_send failed. Retcode: {result_code}. {comment}'

    order_id = getattr(result, 'order', '') or getattr(result, 'deal', '')
    return True, f'Closed follower position {position_ticket}, order {order_id}'


def _find_position_to_close(client, copied_event: SyncEvent) -> dict | None:
    """Locate the follower position for a copied event.

    Superseded by explicit ownership matching in Task 6; retained here so this
    task stays a pure connection change.
    """
    target_ids = {copied_event.follower_position_id, copied_event.follower_order_id} - {''}
    try:
        positions = client.positions_get(symbol=copied_event.symbol) or client.positions_get() or []
    except TypeError:
        positions = client.positions_get() or []

    fallback = None
    for position in positions:
        payload = position._asdict() if hasattr(position, '_asdict') else dict(position)
        ticket = str(payload.get('ticket') or '')
        identifier = str(payload.get('identifier') or '')
        if ticket in target_ids or identifier in target_ids:
            return payload
        if fallback is None and str(payload.get('symbol') or '').casefold() == copied_event.symbol.casefold():
            fallback = payload
    return fallback
```

Note that `SyncEvent` must be importable from the module namespace because the test builds it via `follower_executor.SyncEvent`; the import line above provides that.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/python/test_local_copy_trading_follower_executor.py -v`

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/follower_executor.py tests/python/test_local_copy_trading_follower_executor.py
git commit -m "refactor(copy-trading): let callers own the follower MT5 session"
```

---

### Task 4: Group tick work by follower account

**Files:**
- Modify: `python_service/app/local_copy_trading/engine.py`
- Test: `tests/python/test_local_copy_trading_engine.py`

Right now `engine.process_tick` walks relationships in declaration order. If one follower has two relationships separated by another follower's relationship, the executor reconnects on every call. Sorting the pending work by follower account makes each account's work contiguous, which the session layer then serves from one connection. The function signature does not change, so existing engine tests keep passing.

- [ ] **Step 1: Add the failing test**

Append to `tests/python/test_local_copy_trading_engine.py`:

```python
def test_engine_groups_copy_actions_by_follower_account():
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[
            Account(id='src-1', name='Main'),
            Account(id='fol-a', name='Follower A'),
            Account(id='fol-b', name='Follower B'),
        ],
        relationships=[
            CopyRelationship(id='rel-a1', source_account_id='src-1', follower_account_id='fol-a', symbol='XAUUSD'),
            CopyRelationship(id='rel-b1', source_account_id='src-1', follower_account_id='fol-b', symbol='EURUSD'),
            CopyRelationship(id='rel-a2', source_account_id='src-1', follower_account_id='fol-a', symbol='GBPUSD'),
        ],
    )
    source_positions = [
        {'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'},
        {'position_id': 'pos-2', 'source_account_id': 'src-1', 'symbol': 'EURUSD'},
        {'position_id': 'pos-3', 'source_account_id': 'src-1', 'symbol': 'GBPUSD'},
    ]
    visited = []

    def fake_copy(follower, relationship, position):
        visited.append(follower.id)
        return True, 'ok', f"fp-{position['position_id']}", ''

    process_tick(state, source_positions, execute_copy=fake_copy)

    assert visited == ['fol-a', 'fol-a', 'fol-b']


def test_engine_groups_close_actions_by_follower_account():
    state = LocalCopyTradingState(
        enabled=True,
        accounts=[
            Account(id='src-1', name='Main'),
            Account(id='fol-a', name='Follower A'),
            Account(id='fol-b', name='Follower B'),
        ],
        relationships=[
            CopyRelationship(id='rel-a1', source_account_id='src-1', follower_account_id='fol-a', symbol='XAUUSD'),
            CopyRelationship(id='rel-b1', source_account_id='src-1', follower_account_id='fol-b', symbol='EURUSD'),
            CopyRelationship(id='rel-a2', source_account_id='src-1', follower_account_id='fol-a', symbol='GBPUSD'),
        ],
    )

    def fake_copy(follower, relationship, position):
        return True, 'ok', f"fp-{position['position_id']}", ''

    source_positions = [
        {'position_id': 'pos-1', 'source_account_id': 'src-1', 'symbol': 'XAUUSD'},
        {'position_id': 'pos-2', 'source_account_id': 'src-1', 'symbol': 'EURUSD'},
        {'position_id': 'pos-3', 'source_account_id': 'src-1', 'symbol': 'GBPUSD'},
    ]
    process_tick(state, source_positions, execute_copy=fake_copy)

    closed = []

    def fake_close(follower, relationship, copied_event):
        closed.append(follower.id)
        return True, 'closed'

    process_tick(state, [], execute_close=fake_close)

    assert closed == ['fol-a', 'fol-a', 'fol-b']
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/python/test_local_copy_trading_engine.py -v -k groups`

Expected: FAIL. `visited` comes back as `['fol-a', 'fol-b', 'fol-a']` because relationships are walked in declaration order.

- [ ] **Step 3: Reorder the tick**

In `python_service/app/local_copy_trading/engine.py`, replace `process_tick` with:

```python
def process_tick(
    state: LocalCopyTradingState,
    source_positions: list[dict],
    execute_copy: CopyExecutor | None = None,
    execute_close: CloseExecutor | None = None,
) -> list[SyncEvent]:
    """Run one synchronisation tick.

    Work is grouped by follower account before execution so that a follower
    holding several relationships only pays for one MT5 connection.
    """
    copy_executor = execute_copy or _default_copy_executor
    close_executor = execute_close or _default_close_executor
    active_accounts = {account.id: account for account in state.accounts if account.is_active}
    events: list[SyncEvent] = []
    active_source_position_ids = {
        str(position.get('position_id') or position.get('ticket') or '')
        for position in source_positions
        if str(position.get('position_id') or position.get('ticket') or '')
    }

    relationships = {relationship.id: relationship for relationship in state.relationships if relationship.is_active}
    pending_closes: list[SyncEvent] = []
    for copied_event in get_open_copied_events(state):
        if copied_event.position_id in active_source_position_ids:
            continue
        relationship = relationships.get(copied_event.relationship_id)
        follower = active_accounts.get(copied_event.follower_account_id)
        if relationship is None or follower is None:
            continue
        pending_closes.append(copied_event)

    pending_copies: list[tuple[str, CopyRelationship, dict]] = []
    for relationship in state.relationships:
        follower = active_accounts.get(relationship.follower_account_id)
        if not relationship.is_active or follower is None or relationship.source_account_id not in active_accounts:
            continue
        for position in source_positions:
            if relationship.source_account_id != position.get('source_account_id'):
                continue
            if relationship.source_symbol.casefold() != str(position.get('symbol') or '').strip().casefold():
                continue
            position_id = str(position.get('position_id') or position.get('ticket') or '')
            if not position_id:
                continue
            if has_copied_position(
                state,
                relationship_id=relationship.id,
                source_account_id=relationship.source_account_id,
                follower_account_id=relationship.follower_account_id,
                position_id=position_id,
            ):
                continue
            pending_copies.append((follower.id, relationship, position))

    for _, relationship, position in sorted(pending_copies, key=lambda item: item[0]):
        follower = active_accounts[relationship.follower_account_id]
        position_id = str(position.get('position_id') or position.get('ticket') or '')
        is_copied, message, follower_position_id, follower_order_id = _copy_result_parts(
            copy_executor(follower, relationship, position)
        )
        event = SyncEvent(
            relationship_id=relationship.id,
            source_account_id=relationship.source_account_id,
            follower_account_id=relationship.follower_account_id,
            position_id=position_id,
            follower_position_id=follower_position_id,
            follower_order_id=follower_order_id,
            symbol=relationship.follower_symbol,
            status='copied' if is_copied else 'failed',
            message=message,
            created_at=utc_now_iso(),
        )
        add_event(state, event)
        events.append(state.events[-1])

    for copied_event in sorted(pending_closes, key=lambda item: item.follower_account_id):
        relationship = relationships[copied_event.relationship_id]
        follower = active_accounts[copied_event.follower_account_id]
        is_closed, close_message = close_executor(follower, relationship, copied_event)
        close_event = SyncEvent(
            relationship_id=copied_event.relationship_id,
            source_account_id=copied_event.source_account_id,
            follower_account_id=copied_event.follower_account_id,
            position_id=copied_event.position_id,
            follower_position_id=copied_event.follower_position_id,
            follower_order_id=copied_event.follower_order_id,
            symbol=copied_event.symbol,
            status='closed' if is_closed else 'failed',
            message=close_message,
            created_at=utc_now_iso(),
        )
        add_event(state, close_event)
        events.append(state.events[-1])

    return events
```

Two ordering changes are deliberate and must be preserved:

1. Closes are collected first but executed after copies. The original code also processed closes before copies; keeping closes last means a same-tick close-then-reopen of the same symbol cannot race with the new open. This also matches the assertion order in `test_engine_groups_close_actions_by_follower_account`.
2. Both lists are stably sorted by follower account id, so work within one account keeps its original relative order.

- [ ] **Step 4: Run the full engine test file**

Run: `python -m pytest tests/python/test_local_copy_trading_engine.py -v`

Expected: `10 passed` — the eight pre-existing engine tests plus the two added here. None of the eight may be modified; this task only reorders execution.

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/engine.py tests/python/test_local_copy_trading_engine.py
git commit -m "perf(copy-trading): group tick work by follower account"
```

---

### Task 5: Persist the order map in SQLite

**Files:**
- Create: `python_service/app/local_copy_trading/copy_trading_db.py`
- Test: `tests/python/test_copy_trading_db.py`

The order map records "this follower position was opened for this source position". It must survive a restart, which the current in-memory event list does not. The `UNIQUE` constraint on `client_key` is the mechanism that makes a retry after a crash a no-op instead of a duplicate position.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_copy_trading_db.py`:

```python
from python_service.app.local_copy_trading import copy_trading_db


def _insert(db_path, client_key='rel-1:pos-1', **overrides):
    fields = {
        'client_key': client_key,
        'relationship_id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'source_position_id': 'pos-1',
        'created_at': '2026-09-18T00:00:00+00:00',
        'db_path': db_path,
    }
    fields.update(overrides)
    return copy_trading_db.insert_pending(**fields)


def test_insert_pending_records_an_intended_order(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)

    inserted = _insert(db)

    assert inserted is True
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'pending'
    assert record['follower_position_ticket'] == ''


def test_insert_pending_is_idempotent_for_the_same_client_key(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)

    first = _insert(db)
    second = _insert(db)

    assert first is True
    assert second is False


def test_confirm_order_records_the_follower_position(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)

    copy_trading_db.confirm_order(
        'rel-1:pos-1',
        follower_position_ticket='789',
        follower_order_id='456',
        message='Copied XAUUSD',
        updated_at='2026-09-18T00:00:01+00:00',
        db_path=db,
    )

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
    assert record['follower_position_ticket'] == '789'
    assert record['follower_order_id'] == '456'


def test_confirm_order_keeps_existing_tickets_when_none_supplied(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)
    copy_trading_db.confirm_order(
        'rel-1:pos-1',
        follower_position_ticket='789',
        follower_order_id='456',
        updated_at='2026-09-18T00:00:01+00:00',
        db_path=db,
    )

    copy_trading_db.confirm_order('rel-1:pos-1', updated_at='2026-09-18T00:00:02+00:00', db_path=db)

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['follower_position_ticket'] == '789'
    assert record['follower_order_id'] == '456'


def test_mark_failed_records_the_reason(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db)

    copy_trading_db.mark_failed(
        'rel-1:pos-1',
        message='Retcode: 10004',
        updated_at='2026-09-18T00:00:02+00:00',
        db_path=db,
    )

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'failed'
    assert record['message'] == 'Retcode: 10004'


def test_list_open_records_excludes_settled_statuses(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db, client_key='rel-1:pos-1')
    _insert(db, client_key='rel-1:pos-2')
    _insert(db, client_key='rel-1:pos-3')
    copy_trading_db.mark_failed(
        'rel-1:pos-3', message='nope', updated_at='2026-09-18T00:00:03+00:00', db_path=db
    )

    open_keys = [record['client_key'] for record in copy_trading_db.list_open_records(db_path=db)]

    assert open_keys == ['rel-1:pos-1', 'rel-1:pos-2']


def test_delete_by_relationship_removes_only_that_relationship(tmp_path):
    db = tmp_path / 'copy.db'
    copy_trading_db.init_db(db)
    _insert(db, client_key='rel-1:pos-1', relationship_id='rel-1')
    _insert(db, client_key='rel-2:pos-1', relationship_id='rel-2')

    copy_trading_db.delete_by_relationship('rel-1', db_path=db)

    assert copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db) is None
    assert copy_trading_db.find_by_client_key('rel-2:pos-1', db_path=db) is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_copy_trading_db.py -v`

Expected: collection error, `ModuleNotFoundError: No module named 'python_service.app.local_copy_trading.copy_trading_db'`

- [ ] **Step 3: Write the implementation**

Create `python_service/app/local_copy_trading/copy_trading_db.py`:

```python
"""SQLite persistence for the local copy trading order map.

The order map is the authoritative record of "this follower position was opened
for this source position". It has to survive process restarts, because the
whole point is to recognise an order that was already sent before a crash.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path('storage/local_copy_trading.db')

OPEN_STATUSES = ('pending', 'confirmed')

_SCHEMA = """
CREATE TABLE IF NOT EXISTS copy_order_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_key TEXT NOT NULL UNIQUE,
    relationship_id TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    follower_account_id TEXT NOT NULL,
    source_position_id TEXT NOT NULL,
    status TEXT NOT NULL,
    follower_position_ticket TEXT NOT NULL DEFAULT '',
    follower_order_id TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_copy_order_map_lookup
    ON copy_order_map (relationship_id, source_position_id);
CREATE INDEX IF NOT EXISTS idx_copy_order_map_status
    ON copy_order_map (status);
CREATE INDEX IF NOT EXISTS idx_copy_order_map_follower
    ON copy_order_map (follower_account_id);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    connection = connect(db_path)
    try:
        connection.executescript(_SCHEMA)
        connection.commit()
    finally:
        connection.close()


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def insert_pending(
    *,
    client_key: str,
    relationship_id: str,
    source_account_id: str,
    follower_account_id: str,
    source_position_id: str,
    created_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> bool:
    """Record an intended order.

    Returns True when a new row was created and False when the client key was
    already present, which is how a retry after a crash is recognised.
    """
    connection = connect(db_path)
    try:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO copy_order_map (
                client_key, relationship_id, source_account_id, follower_account_id,
                source_position_id, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                client_key,
                relationship_id,
                source_account_id,
                follower_account_id,
                source_position_id,
                created_at,
                created_at,
            ),
        )
        connection.commit()
        return cursor.rowcount == 1
    finally:
        connection.close()


def _set_status(
    client_key: str,
    status: str,
    *,
    message: str,
    updated_at: str,
    follower_position_ticket: str = '',
    follower_order_id: str = '',
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    connection = connect(db_path)
    try:
        connection.execute(
            """
            UPDATE copy_order_map
               SET status = ?,
                   message = ?,
                   updated_at = ?,
                   follower_position_ticket = CASE WHEN ? <> '' THEN ? ELSE follower_position_ticket END,
                   follower_order_id = CASE WHEN ? <> '' THEN ? ELSE follower_order_id END
             WHERE client_key = ?
            """,
            (
                status,
                message,
                updated_at,
                follower_position_ticket,
                follower_position_ticket,
                follower_order_id,
                follower_order_id,
                client_key,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def confirm_order(
    client_key: str,
    *,
    follower_position_ticket: str = '',
    follower_order_id: str = '',
    message: str = '',
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    _set_status(
        client_key,
        'confirmed',
        message=message,
        updated_at=updated_at,
        follower_position_ticket=follower_position_ticket,
        follower_order_id=follower_order_id,
        db_path=db_path,
    )


def mark_failed(
    client_key: str,
    *,
    message: str,
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    _set_status(client_key, 'failed', message=message, updated_at=updated_at, db_path=db_path)


def mark_closed(
    client_key: str,
    *,
    message: str,
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    _set_status(client_key, 'closed', message=message, updated_at=updated_at, db_path=db_path)


def mark_drifted(
    client_key: str,
    *,
    message: str,
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    _set_status(client_key, 'drifted', message=message, updated_at=updated_at, db_path=db_path)


def find_by_client_key(client_key: str, *, db_path: Path | str = DEFAULT_DB_PATH) -> dict | None:
    connection = connect(db_path)
    try:
        row = connection.execute(
            'SELECT * FROM copy_order_map WHERE client_key = ?',
            (client_key,),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        connection.close()


def list_open_records(*, db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    """Return every record that claims a follower position should exist."""
    connection = connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT * FROM copy_order_map
             WHERE status IN (?, ?)
             ORDER BY id
            """,
            OPEN_STATUSES,
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        connection.close()


def delete_by_relationship(relationship_id: str, *, db_path: Path | str = DEFAULT_DB_PATH) -> None:
    connection = connect(db_path)
    try:
        connection.execute(
            'DELETE FROM copy_order_map WHERE relationship_id = ?',
            (relationship_id,),
        )
        connection.commit()
    finally:
        connection.close()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/python/test_copy_trading_db.py -v`

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/copy_trading_db.py tests/python/test_copy_trading_db.py
git commit -m "feat(copy-trading): persist the copy order map in sqlite"
```

---

### Task 6: Identify follower positions by ownership, not by symbol

**Files:**
- Create: `python_service/app/local_copy_trading/position_ownership.py`
- Modify: `python_service/app/local_copy_trading/follower_executor.py`
- Test: `tests/python/test_local_copy_trading_ownership.py`
- Test: `tests/python/test_local_copy_trading_follower_executor.py`

This is the task that removes the risk of closing a position this tool does not own. After it, a follower position is found only by matching the ownership token written into its order comment. When the token does not match, the answer is "nothing to close" — never "some position in the same symbol".

MT5 caps the order comment at 31 characters, so each identifier is hashed to eight hex characters: `lc:<8>:<8>` is 20 characters.

- [ ] **Step 1: Write the failing test for the ownership token**

Create `tests/python/test_local_copy_trading_ownership.py`:

```python
from python_service.app.local_copy_trading import position_ownership


def test_short_token_is_stable_and_eight_characters():
    first = position_ownership.short_token('relationship-1')
    second = position_ownership.short_token('relationship-1')

    assert first == second
    assert len(first) == 8


def test_short_token_distinguishes_inputs():
    assert position_ownership.short_token('pos-1') != position_ownership.short_token('pos-2')


def test_build_comment_stays_within_the_mt5_comment_limit():
    comment = position_ownership.build_comment('rel-1', 'pos-1')

    assert comment.startswith('lc:')
    assert len(comment) <= position_ownership.MAX_COMMENT_LENGTH
    assert len(comment) == 20


def test_build_comment_is_deterministic():
    assert position_ownership.build_comment('rel-1', 'pos-1') == position_ownership.build_comment('rel-1', 'pos-1')


def test_is_owned_position_matches_the_exact_position():
    payload = {
        'ticket': 789,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment('rel-1', 'pos-1'),
    }

    assert position_ownership.is_owned_position(payload, relationship_id='rel-1', position_id='pos-1') is True


def test_is_owned_position_rejects_a_manual_position():
    payload = {'ticket': 111, 'magic': 0, 'comment': position_ownership.build_comment('rel-1', 'pos-1')}

    assert position_ownership.is_owned_position(payload, relationship_id='rel-1', position_id='pos-1') is False


def test_is_owned_position_rejects_a_position_from_another_source_position():
    payload = {
        'ticket': 789,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment('rel-1', 'pos-2'),
    }

    assert position_ownership.is_owned_position(payload, relationship_id='rel-1', position_id='pos-1') is False


def test_is_owned_position_rejects_a_position_from_another_relationship():
    payload = {
        'ticket': 789,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment('rel-2', 'pos-1'),
    }

    assert position_ownership.is_owned_position(payload, relationship_id='rel-1', position_id='pos-1') is False


def test_is_owned_position_rejects_a_position_without_a_comment():
    payload = {'ticket': 789, 'magic': position_ownership.COPY_TRADING_MAGIC, 'comment': None}

    assert position_ownership.is_owned_position(payload, relationship_id='rel-1', position_id='pos-1') is False


def test_select_owned_position_ignores_other_positions_in_the_same_symbol():
    positions = [
        {'ticket': 111, 'symbol': 'XAUUSD', 'magic': 0, 'comment': ''},
        {'ticket': 222, 'symbol': 'XAUUSD', 'magic': 88888, 'comment': 'other-ea'},
        {
            'ticket': 789,
            'symbol': 'XAUUSD',
            'magic': position_ownership.COPY_TRADING_MAGIC,
            'comment': position_ownership.build_comment('rel-1', 'pos-1'),
        },
    ]

    owned = position_ownership.select_owned_position(positions, relationship_id='rel-1', position_id='pos-1')

    assert owned is not None
    assert owned['ticket'] == 789


def test_select_owned_position_returns_none_when_nothing_matches():
    positions = [
        {'ticket': 111, 'symbol': 'XAUUSD', 'magic': 0, 'comment': ''},
        {'ticket': 222, 'symbol': 'XAUUSD', 'magic': 88888, 'comment': 'other-ea'},
    ]

    assert position_ownership.select_owned_position(positions, relationship_id='rel-1', position_id='pos-1') is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_local_copy_trading_ownership.py -v`

Expected: collection error, `ModuleNotFoundError: No module named 'python_service.app.local_copy_trading.position_ownership'`

- [ ] **Step 3: Write the ownership module**

Create `python_service/app/local_copy_trading/position_ownership.py`:

```python
"""Ownership tokens for follower positions.

An MT5 position carries the ``magic`` number and the ``comment`` of the order
that opened it. Those two fields are the only reliable way to tell a position
this tool opened for a specific source position apart from a manual position or
another EA's position in the same symbol.

The comment is capped at 31 characters by MT5, so identifiers are hashed to
eight hex characters each: ``lc:<8>:<8>`` is 20 characters.
"""

from __future__ import annotations

import hashlib

COPY_TRADING_MAGIC = 260526
COMMENT_PREFIX = 'lc'
MAX_COMMENT_LENGTH = 31


def short_token(value: str) -> str:
    """Return a stable eight-character token for an identifier."""
    return hashlib.sha1(str(value or '').encode('utf-8')).hexdigest()[:8]


def build_comment(relationship_id: str, position_id: str) -> str:
    """Build the comment that marks a follower order as owned by a relationship."""
    return f'{COMMENT_PREFIX}:{short_token(relationship_id)}:{short_token(position_id)}'


def is_copy_trading_position(payload: dict) -> bool:
    """True when the position was opened by the copy trading module."""
    return int(payload.get('magic') or 0) == COPY_TRADING_MAGIC


def is_owned_position(payload: dict, *, relationship_id: str, position_id: str) -> bool:
    """True when this exact position belongs to this relationship/source pair."""
    if not is_copy_trading_position(payload):
        return False
    return str(payload.get('comment') or '').strip() == build_comment(relationship_id, position_id)


def select_owned_position(positions, *, relationship_id: str, position_id: str) -> dict | None:
    """Return the follower position owned by the given pair, or None.

    Returning None is a meaningful answer: it means the position is gone or was
    never opened. Callers must not fall back to matching by symbol.
    """
    for payload in positions:
        if is_owned_position(payload, relationship_id=relationship_id, position_id=position_id):
            return payload
    return None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/python/test_local_copy_trading_ownership.py -v`

Expected: `11 passed`

- [ ] **Step 5: Rewrite the executor test to require ownership matching**

Replace the whole of `tests/python/test_local_copy_trading_follower_executor.py` with:

```python
from collections import namedtuple

from python_service.app.local_copy_trading import follower_executor, position_ownership
from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount


Tick = namedtuple('Tick', ['ask', 'bid'])
SymbolInfo = namedtuple('SymbolInfo', ['volume_min', 'volume_step'])
OrderResult = namedtuple('OrderResult', ['retcode', 'order', 'deal', 'comment'])
Position = namedtuple('Position', ['ticket', 'identifier', 'symbol', 'type', 'volume', 'magic', 'comment'])


def _follower(**overrides):
    fields = {
        'id': 'fol-1',
        'name': 'Follower A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'D:/MT5/follower/terminal64.exe',
        'login': '2001',
        'password': 'secret',
        'server': 'Demo',
    }
    fields.update(overrides)
    return FollowerAccount(**fields)


def _relationship(**overrides):
    fields = {
        'id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'symbol': 'XAUUSD',
        'source_symbol': 'XAUUSD',
        'follower_symbol': 'XAUUSD.m',
    }
    fields.update(overrides)
    return CopyRelationship(**fields)


def _owned_position(ticket=789, position_id='pos-1', relationship_id='rel-1', **overrides):
    fields = {
        'ticket': ticket,
        'identifier': ticket,
        'symbol': 'XAUUSD.m',
        'type': 0,
        'volume': 0.2,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment(relationship_id, position_id),
    }
    fields.update(overrides)
    return Position(**fields)


def _copied_event(**overrides):
    fields = {
        'relationship_id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'position_id': 'pos-1',
        'follower_position_id': '789',
        'follower_order_id': '456',
        'symbol': 'XAUUSD.m',
        'status': 'copied',
        'created_at': '2026-09-18T00:00:00+00:00',
    }
    fields.update(overrides)
    return follower_executor.SyncEvent(**fields)


class FakeClient:
    POSITION_TYPE_BUY = 0
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008

    def __init__(self, positions=None):
        self.sent_requests = []
        self._positions = positions if positions is not None else []

    def symbol_select(self, symbol, enabled):
        return enabled is True

    def symbol_info(self, symbol):
        return SymbolInfo(volume_min=0.01, volume_step=0.01)

    def symbol_info_tick(self, symbol):
        return Tick(ask=2301.5, bid=2301.3)

    def order_send(self, request):
        self.sent_requests.append(request)
        return OrderResult(retcode=10009, order=456, deal=0, comment='done')

    def positions_get(self, symbol=None):
        return self._positions

    def last_error(self):
        return (0, 'ok')


def test_copy_position_tags_the_order_with_an_ownership_comment():
    client = FakeClient()

    follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(lot_multiplier=2),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    request = client.sent_requests[0]
    assert request['symbol'] == 'XAUUSD.m'
    assert request['volume'] == 0.2
    assert request['magic'] == position_ownership.COPY_TRADING_MAGIC
    assert request['comment'] == position_ownership.build_comment('rel-1', 'pos-1')
    assert len(request['comment']) <= position_ownership.MAX_COMMENT_LENGTH


def test_copy_position_reports_the_owned_follower_ticket():
    client = FakeClient(positions=[_owned_position(ticket=789)])

    success, message, follower_position_id, follower_order_id = follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is True
    assert follower_position_id == '789'
    assert follower_order_id == '456'


def test_copy_position_leaves_the_ticket_empty_when_ownership_cannot_be_confirmed():
    client = FakeClient(positions=[_owned_position(ticket=999, position_id='pos-9')])

    success, message, follower_position_id, _ = follower_executor.copy_position_to_follower(
        client,
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is True
    assert follower_position_id == ''


def test_copy_position_reports_symbol_selection_failure():
    class FailingClient(FakeClient):
        def symbol_select(self, symbol, enabled):
            return False

    success, message, _, _ = follower_executor.copy_position_to_follower(
        FailingClient(),
        _follower(),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is False
    assert 'Failed to select follower symbol' in message


def test_copy_position_runs_without_a_follower_connection_for_simulated_accounts():
    success, message, follower_position_id, _ = follower_executor.copy_position_to_follower(
        None,
        _follower(connection_type='simulated'),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is True
    assert follower_position_id == 'pos-1'
    assert 'Simulated copy' in message


def test_copy_position_rejects_unsupported_connection_types():
    success, message, _, _ = follower_executor.copy_position_to_follower(
        None,
        _follower(connection_type='mt5_api'),
        _relationship(),
        {'position_id': 'pos-1', 'symbol': 'XAUUSD', 'volume': 0.1, 'type': 0},
    )

    assert success is False
    assert 'Unsupported follower connection type' in message


def test_close_position_closes_only_the_owned_position():
    client = FakeClient(
        positions=[
            _owned_position(ticket=111, position_id='pos-9'),
            Position(ticket=222, identifier=222, symbol='XAUUSD.m', type=0, volume=0.5, magic=0, comment=''),
            _owned_position(ticket=789, position_id='pos-1', volume=0.2),
        ]
    )

    success, message = follower_executor.close_copied_position_on_follower(
        client,
        _follower(),
        _relationship(),
        _copied_event(),
    )

    assert success is True
    assert len(client.sent_requests) == 1
    request = client.sent_requests[0]
    assert request['position'] == 789
    assert request['volume'] == 0.2
    assert request['type'] == FakeClient.ORDER_TYPE_SELL


def test_close_position_does_not_send_an_order_when_nothing_is_owned():
    client = FakeClient(
        positions=[
            Position(ticket=222, identifier=222, symbol='XAUUSD.m', type=0, volume=0.5, magic=0, comment=''),
            _owned_position(ticket=111, position_id='pos-9'),
        ]
    )

    success, message = follower_executor.close_copied_position_on_follower(
        client,
        _follower(),
        _relationship(),
        _copied_event(),
    )

    assert success is True
    assert client.sent_requests == []
    assert 'nothing to close' in message


def test_close_position_requires_the_relationship_to_match():
    client = FakeClient(positions=[_owned_position(ticket=789, relationship_id='rel-2')])

    success, message = follower_executor.close_copied_position_on_follower(
        client,
        _follower(),
        _relationship(),
        _copied_event(),
    )

    assert success is True
    assert client.sent_requests == []
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_local_copy_trading_follower_executor.py -v`

Expected: FAIL. The order comment is still `local-copy:<id>` and closes still fall back to symbol matching, so the ownership assertions fail.

- [ ] **Step 7: Rewrite the executor to use ownership tokens**

Replace the whole of `python_service/app/local_copy_trading/follower_executor.py` with:

```python
"""Execute follower-side MT5 orders against an already-open session.

The caller owns the connection (see ``services.mt5_session``). This module only
builds and validates order requests, so it can be tested without a terminal.

Follower positions are identified by the ownership token written into the order
comment (see ``position_ownership``). There is deliberately no symbol-based
fallback: matching the wrong position on a live account is worse than reporting
that nothing was found.
"""

import math

from python_service.app.local_copy_trading import position_ownership
from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount, SyncEvent


def _as_dict(value) -> dict:
    if hasattr(value, '_asdict'):
        return value._asdict()
    if isinstance(value, dict):
        return value
    return dict(value)


def _position_is_buy(position: dict, client) -> bool:
    value = position.get('type')
    if isinstance(value, str):
        return value.strip().casefold() in {'buy', 'long', '0'}
    return int(value or 0) == getattr(client, 'POSITION_TYPE_BUY', 0)


def _normalize_volume(raw_volume: float, symbol_info) -> float:
    if raw_volume <= 0:
        raise ValueError('copy volume must be greater than 0')
    volume_min = float(getattr(symbol_info, 'volume_min', 0.01) or 0.01)
    volume_step = float(getattr(symbol_info, 'volume_step', 0.01) or 0.01)
    volume = max(raw_volume, volume_min)
    steps = math.floor((volume - volume_min) / volume_step + 0.000001)
    normalized = volume_min + steps * volume_step
    return round(max(normalized, volume_min), 8)


def _done_codes(client) -> set:
    return {
        getattr(client, 'TRADE_RETCODE_DONE', 10009),
        getattr(client, 'TRADE_RETCODE_PLACED', 10008),
    }


def find_owned_position(
    client,
    symbol: str,
    *,
    relationship_id: str,
    position_id: str,
) -> dict | None:
    """Locate the follower position owned by this relationship/source pair.

    Returns None when the position is absent. Callers must treat None as
    "nothing to act on" rather than falling back to another position.
    """
    try:
        positions = client.positions_get(symbol=symbol)
    except TypeError:
        positions = client.positions_get()
    except Exception:
        return None

    return position_ownership.select_owned_position(
        [_as_dict(position) for position in (positions or [])],
        relationship_id=relationship_id,
        position_id=position_id,
    )


def copy_position_to_follower(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
) -> tuple[bool, str, str, str]:
    """Open a follower position mirroring ``source_position``.

    Returns ``(success, message, follower_position_id, follower_order_id)``.
    """
    if follower.connection_type == 'simulated':
        return True, f'Simulated copy {relationship.source_symbol} to {relationship.follower_symbol}', source_position.get('position_id', ''), ''
    if follower.connection_type != 'mt5_terminal':
        return False, f'Unsupported follower connection type: {follower.connection_type}', '', ''

    position_id = str(source_position.get('position_id') or source_position.get('ticket') or '')
    if not position_id:
        return False, 'Source position has no identifier', '', ''

    symbol = relationship.follower_symbol
    if not client.symbol_select(symbol, True):
        return False, f'Failed to select follower symbol {symbol}. Error: {client.last_error()}', '', ''

    symbol_info = client.symbol_info(symbol)
    tick = client.symbol_info_tick(symbol)
    if symbol_info is None or tick is None:
        return False, f'Missing tick or symbol info for follower symbol {symbol}. Error: {client.last_error()}', '', ''

    is_buy = _position_is_buy(source_position, client)
    order_type = getattr(client, 'ORDER_TYPE_BUY', 0) if is_buy else getattr(client, 'ORDER_TYPE_SELL', 1)
    price = float(getattr(tick, 'ask', 0) if is_buy else getattr(tick, 'bid', 0))
    if price <= 0:
        return False, f'Missing executable price for follower symbol {symbol}', '', ''

    source_volume = float(source_position.get('volume') or 0)
    try:
        volume = _normalize_volume(source_volume * relationship.lot_multiplier, symbol_info)
    except ValueError as error:
        return False, str(error), '', ''

    request = {
        'action': getattr(client, 'TRADE_ACTION_DEAL', 1),
        'symbol': symbol,
        'volume': volume,
        'type': order_type,
        'price': price,
        'deviation': 20,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment(relationship.id, position_id),
        'type_time': getattr(client, 'ORDER_TIME_GTC', 0),
        'type_filling': getattr(client, 'ORDER_FILLING_IOC', 1),
    }
    result = client.order_send(request)
    if result is None:
        return False, f'MT5 order_send returned no result. Error: {client.last_error()}', '', ''

    result_code = getattr(result, 'retcode', None)
    if result_code not in _done_codes(client):
        comment = getattr(result, 'comment', '')
        return False, f'MT5 order_send failed. Retcode: {result_code}. {comment}', '', ''

    order_id = getattr(result, 'order', '') or getattr(result, 'deal', '')
    owned = find_owned_position(
        client,
        symbol,
        relationship_id=relationship.id,
        position_id=position_id,
    )
    follower_position_id = str(owned.get('ticket') or '') if owned else ''
    return True, f'Copied {relationship.source_symbol} to {symbol}, volume {volume}, order {order_id}', follower_position_id, str(order_id or '')


def close_copied_position_on_follower(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    copied_event: SyncEvent,
) -> tuple[bool, str]:
    """Close the follower position owned by ``copied_event``."""
    if follower.connection_type == 'simulated':
        return True, f'Simulated close {copied_event.follower_position_id or copied_event.position_id}'
    if follower.connection_type != 'mt5_terminal':
        return False, f'Unsupported follower connection type: {follower.connection_type}'

    target_position = find_owned_position(
        client,
        copied_event.symbol,
        relationship_id=relationship.id,
        position_id=copied_event.position_id,
    )
    if target_position is None:
        return True, f'No owned follower position for source position {copied_event.position_id}; nothing to close'

    symbol = str(target_position.get('symbol') or copied_event.symbol or relationship.follower_symbol)
    if not client.symbol_select(symbol, True):
        return False, f'Failed to select follower symbol {symbol}. Error: {client.last_error()}'

    tick = client.symbol_info_tick(symbol)
    if tick is None:
        return False, f'Missing tick for follower symbol {symbol}. Error: {client.last_error()}'

    is_buy = _position_is_buy(target_position, client)
    order_type = getattr(client, 'ORDER_TYPE_SELL', 1) if is_buy else getattr(client, 'ORDER_TYPE_BUY', 0)
    price = float(getattr(tick, 'bid', 0) if is_buy else getattr(tick, 'ask', 0))
    if price <= 0:
        return False, f'Missing close price for follower symbol {symbol}'

    position_ticket = int(target_position.get('ticket') or 0)
    volume = float(target_position.get('volume') or 0)
    if position_ticket <= 0 or volume <= 0:
        return False, f'Invalid follower position data for {symbol}'

    request = {
        'action': getattr(client, 'TRADE_ACTION_DEAL', 1),
        'symbol': symbol,
        'volume': volume,
        'type': order_type,
        'position': position_ticket,
        'price': price,
        'deviation': 20,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment(relationship.id, copied_event.position_id),
        'type_time': getattr(client, 'ORDER_TIME_GTC', 0),
        'type_filling': getattr(client, 'ORDER_FILLING_IOC', 1),
    }
    result = client.order_send(request)
    if result is None:
        return False, f'MT5 close order_send returned no result. Error: {client.last_error()}'

    result_code = getattr(result, 'retcode', None)
    if result_code not in _done_codes(client):
        comment = getattr(result, 'comment', '')
        return False, f'MT5 close order_send failed. Retcode: {result_code}. {comment}'

    order_id = getattr(result, 'order', '') or getattr(result, 'deal', '')
    return True, f'Closed follower position {position_ticket}, order {order_id}'
```

- [ ] **Step 8: Run the executor tests to verify they pass**

Run: `python -m pytest tests/python/test_local_copy_trading_follower_executor.py -v`

Expected: `9 passed`

- [ ] **Step 9: Commit**

```bash
git add python_service/app/local_copy_trading/position_ownership.py python_service/app/local_copy_trading/follower_executor.py tests/python/test_local_copy_trading_ownership.py tests/python/test_local_copy_trading_follower_executor.py
git commit -m "fix(copy-trading): resolve follower positions by ownership token"
```

---

### Task 7: Make copy actions idempotent across crashes

**Files:**
- Create: `python_service/app/local_copy_trading/copy_service.py`
- Test: `tests/python/test_local_copy_trading_copy_service.py`

This task wires the database into the copy path with a two-phase write: record the intent, send the order, then settle the record. `engine.process_tick` keeps its current executor signature and knows nothing about either persistence or connections.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_local_copy_trading_copy_service.py`:

```python
import contextlib

import pytest

from python_service.app.local_copy_trading import copy_service, copy_trading_db
from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount, SyncEvent
from python_service.app.services.mt5_session import Mt5SessionError


class FakeClient:
    """Placeholder for the MetaTrader5 module handed out by the session."""


def _follower(**overrides):
    fields = {
        'id': 'fol-1',
        'name': 'Follower A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'D:/MT5/follower/terminal64.exe',
        'login': '2001',
        'password': 'secret',
        'server': 'Demo',
    }
    fields.update(overrides)
    return FollowerAccount(**fields)


def _relationship(**overrides):
    fields = {
        'id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'symbol': 'XAUUSD',
        'source_symbol': 'XAUUSD',
        'follower_symbol': 'XAUUSD.m',
    }
    fields.update(overrides)
    return CopyRelationship(**fields)


def _copied_event(**overrides):
    fields = {
        'relationship_id': 'rel-1',
        'source_account_id': 'src-1',
        'follower_account_id': 'fol-1',
        'position_id': 'pos-1',
        'follower_position_id': '789',
        'follower_order_id': '456',
        'symbol': 'XAUUSD.m',
        'status': 'copied',
        'created_at': '2026-09-18T00:00:00+00:00',
    }
    fields.update(overrides)
    return SyncEvent(**fields)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'copy.db'
    copy_trading_db.init_db(path)
    return path


@pytest.fixture
def session(monkeypatch):
    @contextlib.contextmanager
    def fake_use_account(*args, **kwargs):
        yield FakeClient()

    monkeypatch.setattr(copy_service, 'use_account', fake_use_account)


def _seed_confirmed(db, client_key='rel-1:pos-1', ticket='789'):
    copy_trading_db.insert_pending(
        client_key=client_key,
        relationship_id='rel-1',
        source_account_id='src-1',
        follower_account_id='fol-1',
        source_position_id='pos-1',
        created_at='2026-09-18T00:00:00+00:00',
        db_path=db,
    )
    copy_trading_db.confirm_order(
        client_key,
        follower_position_ticket=ticket,
        follower_order_id='456',
        message='Copied',
        updated_at='2026-09-18T00:00:01+00:00',
        db_path=db,
    )


def test_execute_copy_records_a_confirmed_order(db, session, monkeypatch):
    monkeypatch.setattr(
        copy_service.follower_executor,
        'copy_position_to_follower',
        lambda client, follower, relationship, position: (True, 'Copied', '789', '456'),
    )

    result = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1', 'volume': 0.1}, db_path=db
    )

    assert result == (True, 'Copied', '789', '456')
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
    assert record['follower_position_ticket'] == '789'


def test_execute_copy_does_not_send_a_second_order_for_the_same_position(db, session, monkeypatch):
    sent = []

    def fake_copy(client, follower, relationship, position):
        sent.append(position['position_id'])
        return True, 'Copied', '789', '456'

    monkeypatch.setattr(copy_service.follower_executor, 'copy_position_to_follower', fake_copy)

    copy_service.execute_copy(_follower(), _relationship(), {'position_id': 'pos-1'}, db_path=db)
    second = copy_service.execute_copy(_follower(), _relationship(), {'position_id': 'pos-1'}, db_path=db)

    assert sent == ['pos-1']
    assert second[0] is True
    assert 'Already copied' in second[1]


def test_execute_copy_skips_a_position_confirmed_before_a_crash(db, session, monkeypatch):
    """A row written before the crash must suppress the order, not repeat it."""
    _seed_confirmed(db)

    def exploding_copy(*args, **kwargs):
        raise AssertionError('a second order must not be sent')

    monkeypatch.setattr(copy_service.follower_executor, 'copy_position_to_follower', exploding_copy)

    success, message, follower_position_id, _ = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1'}, db_path=db
    )

    assert success is True
    assert follower_position_id == '789'
    assert 'Already copied' in message


def test_execute_copy_marks_the_row_failed_when_the_order_is_rejected(db, session, monkeypatch):
    monkeypatch.setattr(
        copy_service.follower_executor,
        'copy_position_to_follower',
        lambda *args: (False, 'Retcode: 10004', '', ''),
    )

    success, message, _, _ = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1'}, db_path=db
    )

    assert success is False
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'failed'
    assert record['message'] == 'Retcode: 10004'


def test_execute_copy_marks_the_row_failed_when_the_session_fails(db, monkeypatch):
    def failing_use_account(*args, **kwargs):
        raise Mt5SessionError('login failed')

    monkeypatch.setattr(copy_service, 'use_account', failing_use_account)

    success, message, _, _ = copy_service.execute_copy(
        _follower(), _relationship(), {'position_id': 'pos-1'}, db_path=db
    )

    assert success is False
    assert 'login failed' in message
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'failed'


def test_execute_copy_rejects_a_position_without_an_identifier(db, session):
    success, message, _, _ = copy_service.execute_copy(_follower(), _relationship(), {}, db_path=db)

    assert success is False
    assert 'no identifier' in message


def test_execute_close_settles_the_order_map_row(db, session, monkeypatch):
    _seed_confirmed(db)
    monkeypatch.setattr(
        copy_service.follower_executor,
        'close_copied_position_on_follower',
        lambda *args: (True, 'Closed follower position 789, order 999'),
    )

    success, message = copy_service.execute_close(_follower(), _relationship(), _copied_event(), db_path=db)

    assert success is True
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'closed'


def test_execute_close_leaves_the_row_open_when_the_close_fails(db, session, monkeypatch):
    _seed_confirmed(db)
    monkeypatch.setattr(
        copy_service.follower_executor,
        'close_copied_position_on_follower',
        lambda *args: (False, 'Retcode: 10006'),
    )

    success, message = copy_service.execute_close(_follower(), _relationship(), _copied_event(), db_path=db)

    assert success is False
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_local_copy_trading_copy_service.py -v`

Expected: collection error, `ModuleNotFoundError: No module named 'python_service.app.local_copy_trading.copy_service'`

- [ ] **Step 3: Write the implementation**

Create `python_service/app/local_copy_trading/copy_service.py`:

```python
"""Idempotent copy and close actions.

This is the layer that makes a copy action safe to retry. Before an order is
sent, the intent is written to SQLite keyed by ``<relationship>:<source
position>``. The key is unique, so a retry after a crash finds the existing row
instead of opening a second position.

``engine.process_tick`` talks to these two functions and knows nothing about
persistence or connections.
"""

from __future__ import annotations

from pathlib import Path

from python_service.app.local_copy_trading import copy_trading_db, follower_executor
from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount, SyncEvent
from python_service.app.local_copy_trading.runtime import utc_now_iso
from python_service.app.services.mt5_session import Mt5SessionError, use_account


def build_client_key(relationship_id: str, source_position_id: str) -> str:
    """Identity of one source position copied through one relationship."""
    return f'{relationship_id}:{source_position_id}'


def execute_copy(
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
    *,
    db_path: Path | str = copy_trading_db.DEFAULT_DB_PATH,
) -> tuple[bool, str, str, str]:
    """Copy one source position, at most once, ever."""
    source_position_id = str(source_position.get('position_id') or source_position.get('ticket') or '')
    if not source_position_id:
        return False, 'Source position has no identifier', '', ''

    client_key = build_client_key(relationship.id, source_position_id)
    existing = copy_trading_db.find_by_client_key(client_key, db_path=db_path)
    if existing is not None and existing['status'] == 'confirmed':
        return (
            True,
            f"Already copied as follower position {existing['follower_position_ticket'] or existing['follower_order_id']}",
            existing['follower_position_ticket'] or '',
            existing['follower_order_id'] or '',
        )

    copy_trading_db.insert_pending(
        client_key=client_key,
        relationship_id=relationship.id,
        source_account_id=relationship.source_account_id,
        follower_account_id=relationship.follower_account_id,
        source_position_id=source_position_id,
        created_at=utc_now_iso(),
        db_path=db_path,
    )

    if follower.connection_type == 'mt5_terminal':
        try:
            with use_account(
                follower.terminal_path,
                follower.login,
                follower.password,
                follower.server,
            ) as client:
                result = follower_executor.copy_position_to_follower(
                    client, follower, relationship, source_position
                )
        except Mt5SessionError as error:
            result = (False, str(error), '', '')
    else:
        result = follower_executor.copy_position_to_follower(
            None, follower, relationship, source_position
        )

    success, message, follower_position_id, follower_order_id = result

    if success:
        copy_trading_db.confirm_order(
            client_key,
            follower_position_ticket=follower_position_id,
            follower_order_id=follower_order_id,
            message=message,
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
    else:
        copy_trading_db.mark_failed(
            client_key,
            message=message,
            updated_at=utc_now_iso(),
            db_path=db_path,
        )

    return success, message, follower_position_id, follower_order_id


def execute_close(
    follower: FollowerAccount,
    relationship: CopyRelationship,
    copied_event: SyncEvent,
    *,
    db_path: Path | str = copy_trading_db.DEFAULT_DB_PATH,
) -> tuple[bool, str]:
    """Close a copied follower position and settle its order-map row."""
    if follower.connection_type == 'mt5_terminal':
        try:
            with use_account(
                follower.terminal_path,
                follower.login,
                follower.password,
                follower.server,
            ) as client:
                success, message = follower_executor.close_copied_position_on_follower(
                    client, follower, relationship, copied_event
                )
        except Mt5SessionError as error:
            success, message = False, str(error)
    else:
        success, message = follower_executor.close_copied_position_on_follower(
            None, follower, relationship, copied_event
        )

    if success:
        copy_trading_db.mark_closed(
            build_client_key(relationship.id, copied_event.position_id),
            message=message,
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
    return success, message
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/python/test_local_copy_trading_copy_service.py -v`

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/copy_service.py tests/python/test_local_copy_trading_copy_service.py
git commit -m "feat(copy-trading): make copy actions idempotent via order map"
```

---

### Task 8: Reconcile the order map against live positions

**Files:**
- Create: `python_service/app/local_copy_trading/reconcile.py`
- Test: `tests/python/test_local_copy_trading_reconcile.py`

A crash is not the only way the map and reality diverge: a position can be closed by hand, and a record can be lost. This task repairs the recoverable cases and reports the rest.

The orphan sweep is opt-in because inspecting a follower costs a connection. Every follower with an open record is always inspected (it has something to repair); followers without records are only swept when a caller asks, which is what the startup pass does.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_local_copy_trading_reconcile.py`:

```python
import pytest

from python_service.app.local_copy_trading import copy_trading_db, position_ownership, reconcile
from python_service.app.local_copy_trading.models import Account, CopyRelationship, LocalCopyTradingState


def _follower(**overrides):
    fields = {
        'id': 'fol-1',
        'name': 'Follower A',
        'connection_type': 'mt5_terminal',
        'terminal_path': 'D:/MT5/follower/terminal64.exe',
        'login': '2001',
        'password': 'secret',
        'server': 'Demo',
    }
    fields.update(overrides)
    return Account(**fields)


def _state(**overrides):
    fields = {
        'enabled': True,
        'accounts': [_follower()],
        'relationships': [
            CopyRelationship(
                id='rel-1',
                source_account_id='src-1',
                follower_account_id='fol-1',
                symbol='XAUUSD',
            )
        ],
    }
    fields.update(overrides)
    return LocalCopyTradingState(**fields)


def _positions_for(position_id='pos-1', ticket=789, relationship_id='rel-1'):
    return [
        {
            'ticket': ticket,
            'symbol': 'XAUUSD.m',
            'magic': position_ownership.COPY_TRADING_MAGIC,
            'comment': position_ownership.build_comment(relationship_id, position_id),
        }
    ]


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'copy.db'
    copy_trading_db.init_db(path)
    return path


def _seed(db, status='pending', client_key='rel-1:pos-1'):
    copy_trading_db.insert_pending(
        client_key=client_key,
        relationship_id='rel-1',
        source_account_id='src-1',
        follower_account_id='fol-1',
        source_position_id='pos-1',
        created_at='2026-09-18T00:00:00+00:00',
        db_path=db,
    )
    if status == 'confirmed':
        copy_trading_db.confirm_order(
            client_key,
            follower_position_ticket='789',
            follower_order_id='456',
            updated_at='2026-09-18T00:00:01+00:00',
            db_path=db,
        )


def test_pending_record_is_confirmed_when_the_position_exists(db):
    _seed(db, status='pending')
    state = _state()

    events = reconcile.reconcile(state, db_path=db, positions_reader=lambda follower: _positions_for())

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
    assert record['follower_position_ticket'] == '789'
    assert [event.status for event in events] == ['copied']


def test_confirmed_record_is_marked_drifted_when_the_position_is_gone(db):
    _seed(db, status='confirmed')
    state = _state()

    events = reconcile.reconcile(state, db_path=db, positions_reader=lambda follower: [])

    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'drifted'
    assert [event.status for event in events] == ['failed']
    assert 'Drift' in events[0].message


def test_confirmed_record_with_its_position_produces_no_events(db):
    _seed(db, status='confirmed')
    state = _state()

    events = reconcile.reconcile(state, db_path=db, positions_reader=lambda follower: _positions_for())

    assert events == []
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'


def test_unclaimed_copy_position_is_reported_as_orphan(db):
    state = _state()

    events = reconcile.reconcile(
        state,
        db_path=db,
        positions_reader=lambda follower: _positions_for(position_id='pos-unknown', ticket=555),
        include_orphans=True,
    )

    assert [event.status for event in events] == ['skipped']
    assert 'Orphan' in events[0].message
    assert events[0].follower_position_id == '555'


def test_positions_from_other_software_are_not_reported_as_orphans(db):
    state = _state()

    events = reconcile.reconcile(
        state,
        db_path=db,
        positions_reader=lambda follower: [
            {'ticket': 111, 'symbol': 'XAUUSD.m', 'magic': 0, 'comment': ''},
            {'ticket': 222, 'symbol': 'XAUUSD.m', 'magic': 88888, 'comment': 'other-ea'},
        ],
        include_orphans=True,
    )

    assert events == []


def test_orphan_sweep_is_opt_in(db):
    state = _state()
    calls = []

    def reader(follower):
        calls.append(follower.id)
        return _positions_for(position_id='pos-unknown', ticket=555)

    events = reconcile.reconcile(state, db_path=db, positions_reader=reader)

    assert events == []
    assert calls == []


def test_reader_failure_is_reported_without_raising(db):
    _seed(db, status='confirmed')
    state = _state()

    def failing_reader(follower):
        raise RuntimeError('terminal not reachable')

    events = reconcile.reconcile(state, db_path=db, positions_reader=failing_reader)

    assert len(events) == 1
    assert 'terminal not reachable' in events[0].message
    record = copy_trading_db.find_by_client_key('rel-1:pos-1', db_path=db)
    assert record['status'] == 'confirmed'
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_local_copy_trading_reconcile.py -v`

Expected: collection error, `ModuleNotFoundError: No module named 'python_service.app.local_copy_trading.reconcile'`

- [ ] **Step 3: Write the implementation**

Create `python_service/app/local_copy_trading/reconcile.py`:

```python
"""Reconcile the local order map against live follower positions.

The order map is written before an order is sent, which makes it authoritative
about *intent*. The live terminal is authoritative about *reality*. Whenever
they disagree, this module repairs or reports the difference:

- ``pending`` + position exists   -> the order did go through; confirm it.
- ``confirmed`` + position missing -> the position was closed outside the tool
  or never opened; mark it ``drifted`` and raise an event.
- position exists but no record    -> ``orphan``; report it and change nothing,
  because closing a position nobody claimed is not safe to automate.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from python_service.app.local_copy_trading import copy_trading_db, position_ownership
from python_service.app.local_copy_trading.models import LocalCopyTradingState, SyncEvent
from python_service.app.local_copy_trading.runtime import add_event, utc_now_iso
from python_service.app.services.mt5_session import use_account


PositionsReader = Callable[[object], list[dict]]


def _as_dict(value) -> dict:
    if hasattr(value, '_asdict'):
        return value._asdict()
    if isinstance(value, dict):
        return value
    return dict(value)


def read_follower_positions(follower) -> list[dict]:
    """Default reader: the follower's own live positions."""
    with use_account(
        follower.terminal_path,
        follower.login,
        follower.password,
        follower.server,
    ) as client:
        return [_as_dict(position) for position in (client.positions_get() or [])]


def _event(record: dict, status: str, message: str, symbol: str = '') -> SyncEvent:
    return SyncEvent(
        relationship_id=record['relationship_id'],
        source_account_id=record['source_account_id'],
        follower_account_id=record['follower_account_id'],
        position_id=record['source_position_id'],
        follower_position_id=record['follower_position_ticket'],
        follower_order_id=record['follower_order_id'],
        symbol=symbol,
        status=status,
        message=message,
        created_at=utc_now_iso(),
    )


def _reconcile_follower(
    state: LocalCopyTradingState,
    follower,
    records: list[dict],
    *,
    db_path: Path | str,
    positions_reader: PositionsReader,
) -> list[SyncEvent]:
    events: list[SyncEvent] = []
    try:
        positions = positions_reader(follower)
    except Exception as error:
        add_event(
            state,
            SyncEvent(
                relationship_id='',
                source_account_id='',
                follower_account_id=follower.id,
                symbol='',
                status='failed',
                message=f'Reconciliation could not read follower positions: {error}',
                created_at=utc_now_iso(),
            ),
        )
        return [state.events[-1]]

    known_comments: set[str] = set()

    for record in records:
        known_comments.add(
            position_ownership.build_comment(record['relationship_id'], record['source_position_id'])
        )
        owned = position_ownership.select_owned_position(
            positions,
            relationship_id=record['relationship_id'],
            position_id=record['source_position_id'],
        )

        if record['status'] == 'pending' and owned is not None:
            copy_trading_db.confirm_order(
                record['client_key'],
                follower_position_ticket=str(owned.get('ticket') or ''),
                follower_order_id=record['follower_order_id'] or '',
                message='Reconciled: order had already been placed',
                updated_at=utc_now_iso(),
                db_path=db_path,
            )
            updated = dict(record)
            updated['follower_position_ticket'] = str(owned.get('ticket') or '')
            add_event(state, _event(updated, 'copied', 'Reconciled: order had already been placed', str(owned.get('symbol') or '')))
            events.append(state.events[-1])
            continue

        if record['status'] == 'confirmed' and owned is None:
            copy_trading_db.mark_drifted(
                record['client_key'],
                message='Follower position is missing',
                updated_at=utc_now_iso(),
                db_path=db_path,
            )
            add_event(state, _event(record, 'failed', 'Drift: follower position is missing'))
            events.append(state.events[-1])

    for payload in positions:
        if not position_ownership.is_copy_trading_position(payload):
            continue
        comment = str(payload.get('comment') or '').strip()
        if comment in known_comments:
            continue
        add_event(
            state,
            SyncEvent(
                relationship_id='',
                source_account_id='',
                follower_account_id=follower.id,
                position_id='',
                follower_position_id=str(payload.get('ticket') or ''),
                symbol=str(payload.get('symbol') or ''),
                status='skipped',
                message=f"Orphan follower position {payload.get('ticket')} was not opened by any active record",
                created_at=utc_now_iso(),
            ),
        )
        events.append(state.events[-1])

    return events


def reconcile(
    state: LocalCopyTradingState,
    *,
    db_path: Path | str = copy_trading_db.DEFAULT_DB_PATH,
    positions_reader: PositionsReader | None = None,
    include_orphans: bool = False,
) -> list[SyncEvent]:
    """Repair and report order-map drift.

    Only followers that have open records are inspected by default, because
    inspecting a follower costs a connection and a follower with no records has
    nothing to repair. ``include_orphans`` extends the sweep to every follower
    account; use it for the startup pass and for an explicit user-triggered
    audit, not on every tick.
    """
    reader = positions_reader or read_follower_positions
    accounts = {account.id: account for account in state.accounts}
    records = copy_trading_db.list_open_records(db_path=db_path)

    by_follower: dict[str, list[dict]] = {}
    for record in records:
        by_follower.setdefault(record['follower_account_id'], []).append(record)

    if include_orphans:
        follower_ids = {
            relationship.follower_account_id
            for relationship in state.relationships
            if relationship.is_active
        }
        for follower_id in follower_ids:
            by_follower.setdefault(follower_id, [])

    events: list[SyncEvent] = []
    for follower_id, follower_records in by_follower.items():
        follower = accounts.get(follower_id)
        if follower is None or not follower.is_active:
            continue
        events.extend(
            _reconcile_follower(
                state,
                follower,
                follower_records,
                db_path=db_path,
                positions_reader=reader,
            )
        )
    return events
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/python/test_local_copy_trading_reconcile.py -v`

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/reconcile.py tests/python/test_local_copy_trading_reconcile.py
git commit -m "feat(copy-trading): reconcile the order map against live positions"
```

---

### Task 9: Skip ticks whose source snapshot is unchanged

**Files:**
- Modify: `python_service/app/local_copy_trading/source_adapter.py`
- Test: `tests/python/test_local_copy_trading_snapshot.py`

Every tick currently walks the followers even when the source account has not moved. A signature over the fields that actually affect copying lets the loop skip those ticks entirely, which is what makes the connection reuse from Tasks 1-4 pay off. The signature deliberately excludes volatile fields such as `profit` and `price_open`.

- [ ] **Step 1: Write the failing test**

Create `tests/python/test_local_copy_trading_snapshot.py`:

```python
from python_service.app.local_copy_trading import source_adapter


def _position(**overrides):
    fields = {
        'position_id': 'pos-1',
        'source_account_id': 'src-1',
        'symbol': 'XAUUSD',
        'type': 0,
        'volume': 0.1,
        'sl': 0.0,
        'tp': 0.0,
    }
    fields.update(overrides)
    return fields


def test_signature_is_stable_for_the_same_positions():
    positions = [_position()]

    assert source_adapter.positions_signature(positions) == source_adapter.positions_signature(list(positions))


def test_signature_ignores_position_order():
    first = [_position(position_id='pos-1'), _position(position_id='pos-2')]
    second = [_position(position_id='pos-2'), _position(position_id='pos-1')]

    assert source_adapter.positions_signature(first) == source_adapter.positions_signature(second)


def test_signature_ignores_fields_that_do_not_affect_copying():
    without_extras = [_position()]
    with_extras = [_position(profit=12.5, price_open=2300.0, time=1700000000)]

    assert source_adapter.positions_signature(without_extras) == source_adapter.positions_signature(with_extras)


def test_signature_changes_when_a_position_is_opened():
    before = [_position()]
    after = [_position(), _position(position_id='pos-2')]

    assert source_adapter.positions_signature(before) != source_adapter.positions_signature(after)


def test_signature_changes_when_volume_changes():
    before = [_position(volume=0.1)]
    after = [_position(volume=0.2)]

    assert source_adapter.positions_signature(before) != source_adapter.positions_signature(after)


def test_signature_changes_when_a_protective_level_changes():
    before = [_position(sl=2290.0)]
    after = [_position(sl=2285.0)]

    assert source_adapter.positions_signature(before) != source_adapter.positions_signature(after)


def test_first_tick_always_processes():
    should_process, signature = source_adapter.should_process_tick(None, [_position()])

    assert should_process is True
    assert signature == source_adapter.positions_signature([_position()])


def test_unchanged_snapshot_skips_the_tick():
    _, signature = source_adapter.should_process_tick(None, [_position()])

    should_process, next_signature = source_adapter.should_process_tick(signature, [_position()])

    assert should_process is False
    assert next_signature == signature


def test_changed_snapshot_processes_the_tick():
    _, signature = source_adapter.should_process_tick(None, [_position()])

    should_process, _ = source_adapter.should_process_tick(signature, [_position(), _position(position_id='pos-2')])

    assert should_process is True


def test_an_empty_snapshot_after_a_position_closed_processes_the_tick():
    _, signature = source_adapter.should_process_tick(None, [_position()])

    should_process, next_signature = source_adapter.should_process_tick(signature, [])

    assert should_process is True
    assert next_signature == source_adapter.positions_signature([])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_local_copy_trading_snapshot.py -v`

Expected: FAIL with `AttributeError: module 'python_service.app.local_copy_trading.source_adapter' has no attribute 'positions_signature'`

- [ ] **Step 3: Add the signature helpers**

In `python_service/app/local_copy_trading/source_adapter.py`, add the `json` import so the file starts with:

```python
"""Acquire source-account positions through the shared MT5 session."""

import json

from python_service.app.local_copy_trading.models import LocalCopyTradingState
from python_service.app.services.mt5_session import Mt5SessionError, use_account
```

Then append to the end of the file:

```python
def positions_signature(positions: list[dict]) -> str:
    """Reduce a source snapshot to a comparable value.

    Only fields that can change what the engine would do are included, so
    unrelated churn in the MT5 position payload does not trigger work.
    """
    relevant = sorted(
        (
            str(position.get('source_account_id') or ''),
            str(position.get('position_id') or position.get('ticket') or ''),
            str(position.get('symbol') or ''),
            str(position.get('type') or ''),
            str(position.get('volume') or ''),
            str(position.get('sl') or ''),
            str(position.get('tp') or ''),
        )
        for position in positions
    )
    return json.dumps(relevant, ensure_ascii=False, separators=(',', ':'))


def should_process_tick(previous_signature: str | None, positions: list[dict]) -> tuple[bool, str]:
    """Decide whether this tick needs to touch any follower connection.

    Returns ``(should_process, signature)``. When the source snapshot is
    unchanged there is nothing to open, close, or reconcile, so the tick can be
    skipped without connecting to a single follower.
    """
    signature = positions_signature(positions)
    return signature != previous_signature, signature
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/python/test_local_copy_trading_snapshot.py -v`

Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add python_service/app/local_copy_trading/source_adapter.py tests/python/test_local_copy_trading_snapshot.py
git commit -m "perf(copy-trading): skip ticks with an unchanged source snapshot"
```

---

### Task 10: Wire the loop and lifespan, then verify end to end

**Files:**
- Modify: `python_service/app/local_copy_trading/loop.py`
- Modify: `python_service/app/local_copy_trading/routes.py`
- Modify: `python_service/app/main.py`
- Test: `tests/python/test_local_copy_trading_lifespan.py`

This task connects everything: the loop now uses the idempotent executors and reconciles, the lifespan releases the shared session instead of only shutting MT5 down, and deleting a relationship clears its order-map rows so a re-added relationship cannot inherit stale records.

- [ ] **Step 1: Add the failing lifespan test**

Append to `tests/python/test_local_copy_trading_lifespan.py`:

```python
def test_lifespan_releases_the_shared_mt5_session(monkeypatch):
    released = []

    async def idle_loop():
        await asyncio.Event().wait()

    monkeypatch.setattr(backend_main, 'streaming_loop', idle_loop)
    monkeypatch.setattr(backend_main, 'order_sync_loop', idle_loop)
    monkeypatch.setattr(backend_main, 'local_copy_trading_loop', idle_loop)
    monkeypatch.setattr(backend_main, 'quant_loop', idle_loop)
    monkeypatch.setattr(backend_main, 'get_mt5_client', lambda **kwargs: None)
    monkeypatch.setattr(backend_main, 'release_session', lambda: released.append(1))

    async def run_test():
        async with backend_main.lifespan(backend_main.app):
            pass

    asyncio.run(run_test())

    assert released == [1]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/python/test_local_copy_trading_lifespan.py -v`

Expected: FAIL with `AttributeError: <module 'python_service.app.main'> does not have the attribute 'release_session'`

- [ ] **Step 3: Rewrite the loop**

Replace the whole of `python_service/app/local_copy_trading/loop.py` with:

```python
import asyncio

from python_service.app.local_copy_trading import copy_service, copy_trading_db, reconcile
from python_service.app.local_copy_trading.engine import process_tick
from python_service.app.local_copy_trading.runtime import get_state, set_state, update_last_error, utc_now_iso
from python_service.app.local_copy_trading.source_adapter import get_source_positions, should_process_tick
from python_service.app.local_copy_trading.storage import load_state, save_state


async def local_copy_trading_loop() -> None:
    set_state(load_state())
    copy_trading_db.init_db()
    last_signature = None

    # Startup pass: repair anything the previous process left half-done, and
    # sweep for follower positions no record claims. This is the only pass that
    # inspects followers with no open records.
    try:
        reconcile.reconcile(get_state(), include_orphans=True)
        save_state(get_state())
    except Exception as error:
        update_last_error(get_state(), str(error))

    while True:
        state = get_state()
        try:
            state.last_checked_at = utc_now_iso()
            if state.enabled:
                source_positions = get_source_positions(state)
                should_process, last_signature = should_process_tick(last_signature, source_positions)
                if should_process:
                    process_tick(
                        state,
                        source_positions,
                        execute_copy=copy_service.execute_copy,
                        execute_close=copy_service.execute_close,
                    )
                    reconcile.reconcile(state)
            update_last_error(state, None)
            save_state(state)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            update_last_error(state, str(error))
            save_state(state)
        await asyncio.sleep(max(state.poll_interval_seconds, 0.5))
```

- [ ] **Step 4: Clear order-map rows when a relationship is deleted**

In `python_service/app/local_copy_trading/routes.py`, add the import next to the existing storage import:

```python
from python_service.app.local_copy_trading.copy_trading_db import delete_by_relationship
```

Then change the delete handler to drop the relationship's rows:

```python
@router.delete('/relationships/{relationship_id}')
def delete_relationship(relationship_id: str):
    state = remove_relationship(get_state(), relationship_id)
    delete_by_relationship(relationship_id)
    save_state(state)
    return build_overview(state)
```

- [ ] **Step 5: Release the session on lifespan shutdown**

In `python_service/app/main.py`, add the import alongside the other service imports:

```python
from python_service.app.services.mt5_session import release_session
```

Then replace the final `shutdown_mt5()` call in the `lifespan` finally block so that it reads:

```python
    finally:
        for task in background_tasks:
            task.cancel()
        for task in background_tasks:
            with suppress(asyncio.CancelledError):
                await task
        release_session()
```

`release_session()` shuts the connection down and clears the tracked account key, so the `shutdown_mt5` import is still needed elsewhere in the file — do not remove it.

- [ ] **Step 6: Run the lifespan and route tests**

Run: `python -m pytest tests/python/test_local_copy_trading_lifespan.py tests/python/test_local_copy_trading_routes.py -v`

Expected: all pass, including the new release assertion.

- [ ] **Step 7: Verify the whole copy-trading surface, then the full Python suite**

Run: `python -m pytest tests/python -q -k "local_copy or copy_trading or mt5_session"`

Expected: `72 passed` — this is the complete count for the nine test files this plan creates or rewrites.

Then run the full Python suite to catch regressions elsewhere:

Run: `python -m pytest tests/python -q`

Expected: no failures. Any failure in `test_mt5.py`, `test_mt5_polling.py`, or `test_order_sync_service.py` means the session change leaked into another feature — investigate before committing.

- [ ] **Step 8: Verify no symbol-based fallback remains**

Run: `python -m pytest tests/python/test_local_copy_trading_follower_executor.py -v`

Expected: `9 passed`. Then confirm by inspection:

```bash
grep -rn "fallback" python_service/app/local_copy_trading/
```

Expected: no matches. Any remaining `fallback` in the copy-trading package means a symbol-guessing path survived.

- [ ] **Step 9: Commit**

```bash
git add python_service/app/local_copy_trading/loop.py python_service/app/local_copy_trading/routes.py python_service/app/main.py tests/python/test_local_copy_trading_lifespan.py
git commit -m "feat(copy-trading): wire idempotent executors, reconciliation and session release"
```

---

## Definition of done

Phase 1 is complete when all of the following hold:

1. A tick that copies three positions for one follower performs **one** `initialize` for that follower, not three.
2. A tick whose source snapshot is unchanged performs **zero** follower connections.
3. A follower position is only ever closed when its ownership comment matches; no code path closes a position by symbol.
4. Killing the process between `order_send` and the next tick does not produce a second position for the same source position after restart.
5. `python -m pytest tests/python` passes.

## Notes for the implementer

- **Do not add a `shutdown` call back into the executors.** The session keeps the connection open on purpose. If a test demands a shutdown, the test is asserting the old contract and should be updated.
- **Do not reintroduce a symbol fallback** to make a close test pass. `select_owned_position` returning None is the correct answer when ownership is unknown.
- **The `magic` value 260526 is already in production use** by the current executor. Keep it; changing it would orphan every position opened before this change.
- **`storage/local_copy_trading.db` is new runtime state.** It is created on first loop start and should be treated like `storage/alerts.json` — app state, not source.
- **Existing events in `storage/local_copy_trading.json` are not migrated into SQLite.** The JSON event list keeps working as the UI's read model; the database is the new authority for ownership. Reconciling them is out of scope for Phase 1.
