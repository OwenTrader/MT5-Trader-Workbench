import asyncio
import logging
from datetime import datetime, timezone

from python_service.app.local_copy_trading import copy_service, copy_trading_db, guards, reconcile
from python_service.app.local_copy_trading.engine import has_pending_work, process_tick
from python_service.app.local_copy_trading.models import LocalCopyTradingState
from python_service.app.local_copy_trading.runtime import get_state, set_state, update_last_error, utc_now_iso
from python_service.app.local_copy_trading.source_adapter import get_source_positions, should_process_tick
from python_service.app.local_copy_trading.storage import load_state, save_state
from python_service.app.services import loop_heartbeat as heartbeat


logger = logging.getLogger(__name__)


def _active_position_ids(source_positions: list[dict]) -> set[str]:
    return {
        str(position.get('position_id') or position.get('ticket') or '')
        for position in source_positions
    }


def _daily_open_count(state: LocalCopyTradingState, relationship_id: str, today: str) -> int:
    """Count positions first copied for this relationship today (UTC).

    Volume re-syncs emit further ``copied`` events for the same position, so a
    position counts once, on the day its earliest ``copied`` event was written.
    """
    first_copied_at: dict[str, str] = {}
    for event in state.events:
        if event.relationship_id != relationship_id or event.status != 'copied' or not event.position_id:
            continue
        known = first_copied_at.get(event.position_id)
        if known is None or event.created_at < known:
            first_copied_at[event.position_id] = event.created_at
    return sum(1 for created_at in first_copied_at.values() if created_at[:10] == today)


def _consecutive_failures(state: LocalCopyTradingState, relationship_id: str, active_ids: set[str]) -> int:
    """Count the trailing run of copy failures for this relationship.

    Close and drift failures (their source position is already gone from the
    snapshot) do not feed the breaker: they are not evidence that copying is
    broken.
    """
    count = 0
    for event in reversed(state.events):
        if event.relationship_id != relationship_id:
            continue
        if event.status != 'failed':
            break
        if event.position_id not in active_ids:
            continue
        count += 1
    return count


def _build_copy_executor(state: LocalCopyTradingState, source_positions: list[dict]):
    """Bind the risk settings and per-relationship counters to ``execute_copy``."""
    settings = guards.load_risk_settings()
    active_ids = _active_position_ids(source_positions)
    today = datetime.now(timezone.utc).date().isoformat()

    def execute_copy(follower, relationship, position):
        return copy_service.execute_copy(
            follower,
            relationship,
            position,
            risk_settings=settings,
            daily_open_count=_daily_open_count(state, relationship.id, today),
            consecutive_failures=_consecutive_failures(state, relationship.id, active_ids),
        )

    return execute_copy


def _run_tick(state: LocalCopyTradingState, last_signature: str | None) -> str | None:
    """Run one synchronisation pass. Runs on a worker thread: every MT5 call in
    it blocks for the duration of a network round-trip."""
    state.last_checked_at = utc_now_iso()
    if not state.enabled:
        return last_signature

    source_positions = get_source_positions(state)
    should_process, signature = should_process_tick(last_signature, source_positions)

    # A failed copy or close must be retried even though the source snapshot
    # has not changed; the signature alone would skip those ticks forever.
    outstanding = has_pending_work(state, source_positions, recorded_volume=copy_trading_db.get_recorded_volume)
    if should_process or outstanding:
        process_tick(
            state,
            source_positions,
            execute_copy=_build_copy_executor(state, source_positions),
            execute_close=copy_service.execute_close,
            recorded_volume=copy_trading_db.get_recorded_volume,
        )
        reconcile.reconcile(state)
    return signature


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
        logger.exception('Local copy trading startup reconciliation failed')
        update_last_error(get_state(), str(error))

    while True:
        heartbeat.record('local_copy_trading')
        state = get_state()
        try:
            last_signature = await asyncio.to_thread(_run_tick, state, last_signature)
            update_last_error(state, None)
            save_state(state)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception('Local copy trading tick failed')
            update_last_error(state, str(error))
            save_state(state)
        await asyncio.sleep(max(state.poll_interval_seconds, 0.5))
