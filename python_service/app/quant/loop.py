import asyncio
import logging

from python_service.app.services.loop_heartbeat import record
from python_service.app.quant.runtime import run_enabled_jobs_once


QUANT_LOOP_INTERVAL_SECONDS = 2.0

logger = logging.getLogger(__name__)


async def quant_loop() -> None:
    # A single unhandled error (corrupt jobs.json, MT5 hiccup) must not kill
    # the loop permanently with `enabled` still showing in the UI.
    while True:
        try:
            await run_enabled_jobs_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Quant loop iteration failed')
        record('quant')
        await asyncio.sleep(QUANT_LOOP_INTERVAL_SECONDS)
