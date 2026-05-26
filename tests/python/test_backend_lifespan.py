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


def test_lifespan_registers_parent_watchdog_when_parent_pid_present(monkeypatch):
    async def run_test():
        started = {'watchdog': False}

        async def fake_streaming_loop():
            await asyncio.Event().wait()

        async def fake_order_sync_loop():
            await asyncio.Event().wait()

        async def fake_local_copy_trading_loop():
            await asyncio.Event().wait()

        async def fake_parent_process_watchdog(parent_pid: int, interval_seconds: float = 2.0):
            started['watchdog'] = parent_pid == 4321
            await asyncio.Event().wait()

        monkeypatch.setattr(backend_main, 'streaming_loop', fake_streaming_loop)
        monkeypatch.setattr(backend_main, 'order_sync_loop', fake_order_sync_loop)
        monkeypatch.setattr(backend_main, 'local_copy_trading_loop', fake_local_copy_trading_loop)
        monkeypatch.setattr(backend_main, 'parent_process_watchdog', fake_parent_process_watchdog)
        monkeypatch.setenv('PARENT_PID', '4321')

        async with backend_main.lifespan(backend_main.app):
            await asyncio.sleep(0)

        assert started['watchdog'] is True

    asyncio.run(run_test())


def test_parent_process_watchdog_exits_when_parent_is_gone(monkeypatch):
    exits = {'code': None, 'shutdown': 0}

    monkeypatch.setattr(backend_main, 'is_parent_process_alive', lambda parent_pid: False)
    monkeypatch.setattr(backend_main, 'shutdown_mt5', lambda: exits.__setitem__('shutdown', exits['shutdown'] + 1))
    monkeypatch.setattr(backend_main, 'exit_backend_process', lambda code=0: (_ for _ in ()).throw(SystemExit(code)))

    async def run_test():
        try:
            await backend_main.parent_process_watchdog(4321, interval_seconds=0)
        except SystemExit as error:
            exits['code'] = error.code

    asyncio.run(run_test())

    assert exits['shutdown'] == 1
    assert exits['code'] == 0
