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
                        recorded_volume=copy_trading_db.get_recorded_volume,
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
