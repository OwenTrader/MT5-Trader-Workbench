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


def _event(record: dict, status: str, message: str, symbol: str = '', code: str = '') -> SyncEvent:
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
        code=code,
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
            add_event(state, _event(updated, 'copied', 'Reconciled: order had already been placed', str(owned.get('symbol') or ''), code='reconcile_confirmed'))
            events.append(state.events[-1])
            continue

        if record['status'] == 'confirmed' and owned is None:
            copy_trading_db.mark_drifted(
                record['client_key'],
                message='Follower position is missing',
                updated_at=utc_now_iso(),
                db_path=db_path,
            )
            add_event(state, _event(record, 'failed', 'Drift: follower position is missing', code='reconcile_drift'))
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
                code='orphan',
                created_at=utc_now_iso(),
            ),
        )
        events.append(state.events[-1])

    return events


def reconcile(
    state: LocalCopyTradingState,
    *,
    db_path: Path | str | None = None,
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
