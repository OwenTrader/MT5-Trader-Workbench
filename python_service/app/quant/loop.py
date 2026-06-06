import asyncio

from python_service.app.quant.runtime import run_enabled_jobs_once


QUANT_LOOP_INTERVAL_SECONDS = 2.0


async def quant_loop() -> None:
    while True:
        await run_enabled_jobs_once()
        await asyncio.sleep(QUANT_LOOP_INTERVAL_SECONDS)
