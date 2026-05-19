from python_service.app.local_copy_trading.models import LocalCopyTradingState, SyncEvent
from python_service.app.local_copy_trading.runtime import add_event, has_copied_position, utc_now_iso


def process_tick(state: LocalCopyTradingState, source_positions: list[dict]) -> list[SyncEvent]:
    follower_ids = {account.id for account in state.follower_accounts if account.is_active}
    events: list[SyncEvent] = []
    for relationship in state.relationships:
        if not relationship.is_active or relationship.follower_account_id not in follower_ids:
            continue
        for position in source_positions:
            if relationship.source_account_id != position.get('source_account_id'):
                continue
            if relationship.symbol != str(position.get('symbol') or '').strip().upper():
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
            event = SyncEvent(
                relationship_id=relationship.id,
                source_account_id=relationship.source_account_id,
                follower_account_id=relationship.follower_account_id,
                position_id=position_id,
                symbol=relationship.symbol,
                status='copied',
                created_at=utc_now_iso(),
            )
            add_event(state, event)
            events.append(state.events[-1])
    return events
