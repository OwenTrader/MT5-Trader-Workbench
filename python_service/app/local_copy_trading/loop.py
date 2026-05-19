import asyncio

from python_service.app.local_copy_trading.engine import process_tick
from python_service.app.local_copy_trading.runtime import get_state, set_state, update_last_error, utc_now_iso
from python_service.app.local_copy_trading.source_adapter import get_source_positions
from python_service.app.local_copy_trading.storage import load_state, save_state


async def local_copy_trading_loop() -> None:
    set_state(load_state())
    while True:
        state = get_state()
        try:
            state.last_checked_at = utc_now_iso()
            if state.enabled:
                process_tick(state, get_source_positions(state))
            update_last_error(state, None)
            save_state(state)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            update_last_error(state, str(error))
            save_state(state)
        await asyncio.sleep(max(state.poll_interval_seconds, 0.5))
