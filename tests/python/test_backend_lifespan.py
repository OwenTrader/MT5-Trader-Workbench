import asyncio

from python_service.app import main as backend_main


def test_lifespan_cancels_background_tasks_and_shutdowns_mt5(monkeypatch):
    async def run_test():
        task_started = asyncio.Event()
        task_cancelled = asyncio.Event()
        shutdown_calls = {'count': 0}

        async def fake_streaming_loop():
            task_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                task_cancelled.set()
                raise

        async def fake_order_sync_loop():
            await asyncio.Event().wait()

        def fake_shutdown_mt5():
            shutdown_calls['count'] += 1

        monkeypatch.setattr(backend_main, 'streaming_loop', fake_streaming_loop)
        monkeypatch.setattr(backend_main, 'order_sync_loop', fake_order_sync_loop)
        monkeypatch.setattr(backend_main, 'shutdown_mt5', fake_shutdown_mt5, raising=False)

        async with backend_main.lifespan(backend_main.app):
            await asyncio.wait_for(task_started.wait(), timeout=1)

        await asyncio.wait_for(task_cancelled.wait(), timeout=1)
        assert shutdown_calls['count'] == 1

    asyncio.run(run_test())
