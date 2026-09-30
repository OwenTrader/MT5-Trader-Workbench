from collections.abc import Callable

from python_service.app.local_copy_trading.models import (
    CopyRelationship,
    CopyResult,
    FollowerAccount,
    LocalCopyTradingState,
    SyncEvent,
)
from python_service.app.local_copy_trading.runtime import add_event, get_open_copied_events, has_copied_position, utc_now_iso


CopyExecutor = Callable[[FollowerAccount, CopyRelationship, dict], CopyResult | tuple]
CloseExecutor = Callable[[FollowerAccount, CopyRelationship, SyncEvent], tuple[bool, str]]
VolumeReader = Callable[[str, str], float | None]

# Source sizes reported by a broker are exact lot values, so only a genuine
# change should trigger an adjustment rather than float noise.
VOLUME_EPSILON = 1e-9


def _default_copy_executor(follower: FollowerAccount, relationship: CopyRelationship, position: dict) -> tuple[bool, str]:
    return True, f'Mapped {relationship.source_symbol} to {relationship.follower_symbol}'


def _default_close_executor(follower: FollowerAccount, relationship: CopyRelationship, copied_event: SyncEvent) -> tuple[bool, str]:
    return True, f'Closed copied position {copied_event.follower_position_id or copied_event.follower_order_id or copied_event.position_id}'


def _copy_result_parts(result: CopyResult | tuple) -> tuple[bool, str, str, str, str]:
    """Normalise an executor result into ``(success, message, position, order, status)``.

    Both the structured ``CopyResult`` and the legacy plain tuples are accepted
    so a custom executor can stay a two-line lambda.
    """
    if isinstance(result, CopyResult):
        return result.success, result.message, result.follower_position_id, result.follower_order_id, result.status

    is_success = bool(result[0])
    message = str(result[1] if len(result) > 1 else '')
    follower_position_id = str(result[2] if len(result) > 2 else '')
    follower_order_id = str(result[3] if len(result) > 3 else '')
    status = str(result[4]) if len(result) > 4 else ('copied' if is_success else 'failed')
    return is_success, message, follower_position_id, follower_order_id, status


def _needs_volume_sync(
    state: LocalCopyTradingState,
    relationship: CopyRelationship,
    position: dict,
    *,
    position_id: str,
    recorded_volume: VolumeReader | None,
) -> bool:
    """Decide whether a source position should be handed to the copy executor.

    A position that has never been copied always is. A position that already has
    a follower counterpart is only re-sent when its source size moved, and only
    when a reader can tell us what size we last matched. Without a reader the
    engine cannot tell, and the safe default is to leave the existing position
    alone rather than resize it on a guess.
    """
    already_copied = has_copied_position(
        state,
        relationship_id=relationship.id,
        source_account_id=relationship.source_account_id,
        follower_account_id=relationship.follower_account_id,
        position_id=position_id,
    )
    if not already_copied:
        return True

    if recorded_volume is None:
        return False

    recorded = recorded_volume(relationship.id, position_id)
    if recorded is None or recorded <= 0:
        return False

    current = float(position.get('volume') or 0)
    return abs(float(recorded) - current) > VOLUME_EPSILON


def _collect_pending(
    state: LocalCopyTradingState,
    source_positions: list[dict],
    recorded_volume: VolumeReader | None,
) -> tuple[list[SyncEvent], list[tuple[str, CopyRelationship, dict]]]:
    """Return ``(pending_closes, pending_copies)`` for one tick.

    Shared by :func:`process_tick` and :func:`has_pending_work` so the two can
    never disagree about what counts as outstanding work.
    """
    active_accounts = {account.id: account for account in state.accounts if account.is_active}
    relationships = {relationship.id: relationship for relationship in state.relationships if relationship.is_active}
    active_source_position_ids = {
        str(position.get('position_id') or position.get('ticket') or '')
        for position in source_positions
        if str(position.get('position_id') or position.get('ticket') or '')
    }

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
            if not _needs_volume_sync(
                state,
                relationship,
                position,
                position_id=position_id,
                recorded_volume=recorded_volume,
            ):
                continue
            pending_copies.append((follower.id, relationship, position))

    return pending_closes, pending_copies


def has_pending_work(
    state: LocalCopyTradingState,
    source_positions: list[dict],
    *,
    recorded_volume: VolumeReader | None = None,
) -> bool:
    """True when a tick would attempt at least one copy or close.

    The trading loop uses this to force a tick whose source snapshot signature
    is unchanged: a rejected order or a failed close must be retried, which the
    signature filter alone would never do.
    """
    pending_closes, pending_copies = _collect_pending(state, source_positions, recorded_volume)
    return bool(pending_closes or pending_copies)


def process_tick(
    state: LocalCopyTradingState,
    source_positions: list[dict],
    execute_copy: CopyExecutor | None = None,
    execute_close: CloseExecutor | None = None,
    recorded_volume: VolumeReader | None = None,
) -> list[SyncEvent]:
    """Run one synchronisation tick.

    Work is grouped by follower account before execution so that a follower
    holding several relationships only pays for one MT5 connection.
    """
    copy_executor = execute_copy or _default_copy_executor
    close_executor = execute_close or _default_close_executor
    active_accounts = {account.id: account for account in state.accounts if account.is_active}
    events: list[SyncEvent] = []

    pending_closes, pending_copies = _collect_pending(state, source_positions, recorded_volume)
    relationships = {relationship.id: relationship for relationship in state.relationships if relationship.is_active}

    for _, relationship, position in sorted(pending_copies, key=lambda item: item[0]):
        follower = active_accounts[relationship.follower_account_id]
        position_id = str(position.get('position_id') or position.get('ticket') or '')
        is_copied, message, follower_position_id, follower_order_id, status = _copy_result_parts(
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
            status=status if status in {'copied', 'failed', 'skipped'} else ('copied' if is_copied else 'failed'),
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
