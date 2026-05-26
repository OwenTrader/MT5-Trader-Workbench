from collections.abc import Callable

from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount, LocalCopyTradingState, SyncEvent
from python_service.app.local_copy_trading.runtime import add_event, get_open_copied_events, has_copied_position, utc_now_iso


CopyExecutor = Callable[[FollowerAccount, CopyRelationship, dict], tuple[bool, str] | tuple[bool, str, str, str]]
CloseExecutor = Callable[[FollowerAccount, CopyRelationship, SyncEvent], tuple[bool, str]]


def _default_copy_executor(follower: FollowerAccount, relationship: CopyRelationship, position: dict) -> tuple[bool, str]:
    return True, f'Mapped {relationship.source_symbol} to {relationship.follower_symbol}'


def _default_close_executor(follower: FollowerAccount, relationship: CopyRelationship, copied_event: SyncEvent) -> tuple[bool, str]:
    return True, f'Closed copied position {copied_event.follower_position_id or copied_event.follower_order_id or copied_event.position_id}'


def _copy_result_parts(result: tuple) -> tuple[bool, str, str, str]:
    is_success = bool(result[0])
    message = str(result[1] if len(result) > 1 else '')
    follower_position_id = str(result[2] if len(result) > 2 else '')
    follower_order_id = str(result[3] if len(result) > 3 else '')
    return is_success, message, follower_position_id, follower_order_id


def process_tick(
    state: LocalCopyTradingState,
    source_positions: list[dict],
    execute_copy: CopyExecutor | None = None,
    execute_close: CloseExecutor | None = None,
) -> list[SyncEvent]:
    copy_executor = execute_copy or _default_copy_executor
    close_executor = execute_close or _default_close_executor
    followers = {account.id: account for account in state.follower_accounts if account.is_active}
    events: list[SyncEvent] = []
    active_source_position_ids = {
        str(position.get('position_id') or position.get('ticket') or '')
        for position in source_positions
        if str(position.get('position_id') or position.get('ticket') or '')
    }

    relationships = {relationship.id: relationship for relationship in state.relationships if relationship.is_active}
    for copied_event in get_open_copied_events(state):
        if copied_event.position_id in active_source_position_ids:
            continue
        relationship = relationships.get(copied_event.relationship_id)
        follower = followers.get(copied_event.follower_account_id)
        if relationship is None or follower is None:
            continue
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

    for relationship in state.relationships:
        follower = followers.get(relationship.follower_account_id)
        if not relationship.is_active or follower is None:
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
            is_copied, message, follower_position_id, follower_order_id = _copy_result_parts(copy_executor(follower, relationship, position))
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
    return events
