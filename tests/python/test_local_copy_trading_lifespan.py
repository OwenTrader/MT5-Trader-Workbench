import asyncio

from fastapi.testclient import TestClient

from python_service.app import main as backend_main


def test_lifespan_registers_independent_local_copy_trading_loop(monkeypatch):
    async def run_test():
        started = {'streaming': False, 'order_sync': False, 'local_copy': False}
        cancelled = {'streaming': False, 'order_sync': False, 'local_copy': False}

        async def fake_streaming_loop():
            started['streaming'] = True
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled['streaming'] = True
                raise

        async def fake_order_sync_loop():
            started['order_sync'] = True
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled['order_sync'] = True
                raise

        async def fake_local_copy_trading_loop():
            started['local_copy'] = True
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled['local_copy'] = True
                raise

        monkeypatch.setattr(backend_main, 'streaming_loop', fake_streaming_loop)
        monkeypatch.setattr(backend_main, 'order_sync_loop', fake_order_sync_loop)
        monkeypatch.setattr(backend_main, 'local_copy_trading_loop', fake_local_copy_trading_loop)

        async with backend_main.lifespan(backend_main.app):
            await asyncio.sleep(0)

        assert started == {'streaming': True, 'order_sync': True, 'local_copy': True}
        assert cancelled == {'streaming': True, 'order_sync': True, 'local_copy': True}

    asyncio.run(run_test())


def test_main_app_serves_local_copy_trading_route():
    client = TestClient(backend_main.app)
    response = client.get('/local-copy-trading')

    assert response.status_code == 200
