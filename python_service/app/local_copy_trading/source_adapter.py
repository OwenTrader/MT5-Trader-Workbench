"""Acquire source-account positions through the shared MT5 session."""

import json
import logging

from python_service.app.local_copy_trading.models import LocalCopyTradingState
from python_service.app.services.mt5_session import Mt5SessionError, use_account


logger = logging.getLogger(__name__)


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
    failures: list[str] = []
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
            # One unreachable terminal must not stop the healthy accounts from
            # being copied; only total failure aborts the tick.
            failures.append(f'{account.id}: {error}')
            logger.warning('Failed to read source account %s positions: %s', account.id, error)

    if failures and not positions:
        raise RuntimeError('; '.join(failures))

    return positions


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
