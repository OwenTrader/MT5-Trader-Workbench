import asyncio

from fastapi.testclient import TestClient

from python_service.app import main as backend_main


def test_lifespan_registers_independent_quant_loop(monkeypatch):
    async def run_test():
        started = {'quant': False}
        cancelled = {'quant': False}

        async def fake_streaming_loop():
            await asyncio.Event().wait()

        async def fake_order_sync_loop():
            await asyncio.Event().wait()

        async def fake_local_copy_trading_loop():
            await asyncio.Event().wait()

        async def fake_quant_loop():
            started['quant'] = True
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled['quant'] = True
                raise

        monkeypatch.setattr(backend_main, 'streaming_loop', fake_streaming_loop)
        monkeypatch.setattr(backend_main, 'order_sync_loop', fake_order_sync_loop)
        monkeypatch.setattr(backend_main, 'local_copy_trading_loop', fake_local_copy_trading_loop)
        monkeypatch.setattr(backend_main, 'quant_loop', fake_quant_loop)

        async with backend_main.lifespan(backend_main.app):
            await asyncio.sleep(0)

        assert started['quant'] is True
        assert cancelled['quant'] is True

    asyncio.run(run_test())


def test_main_app_serves_python_quant_route():
    client = TestClient(backend_main.app)
    response = client.get('/python-quant/overview')

    assert response.status_code == 200
