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
