from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from contextlib import asynccontextmanager, suppress

from python_service.app.routes.health import router as health_router
from python_service.app.routes.settings import router as settings_router
from python_service.app.routes.mt5 import router as mt5_router
from python_service.app.routes.overlay import router as overlay_router
from python_service.app.routes.alerts import router as alerts_router
from python_service.app.routes.stream import router as stream_router
from python_service.app.routes.notifications import router as notifications_router
from python_service.app.routes.history import router as history_router
from python_service.app.routes.awakening import router as awakening_router
from python_service.app.routes.order_sync import router as order_sync_router
from python_service.app.routes.risk_control import router as risk_control_router
from python_service.app.local_copy_trading.routes import router as local_copy_trading_router
from python_service.app.services.mt5_service import shutdown_mt5
from python_service.app.services.order_sync_service import order_sync_loop
from python_service.app.services.streaming_service import streaming_loop
from python_service.app.local_copy_trading.loop import local_copy_trading_loop
from python_service.app.local_copy_trading.runtime import set_state as set_local_copy_trading_state
from python_service.app.local_copy_trading.storage import load_state as load_local_copy_trading_state

@asynccontextmanager
async def lifespan(app: FastAPI):
    set_local_copy_trading_state(load_local_copy_trading_state())
    background_tasks = [
        asyncio.create_task(streaming_loop()),
        asyncio.create_task(order_sync_loop()),
        asyncio.create_task(local_copy_trading_loop()),
    ]
    try:
        yield
    finally:
        for task in background_tasks:
            task.cancel()
        for task in background_tasks:
            with suppress(asyncio.CancelledError):
                await task
        shutdown_mt5()

app = FastAPI(lifespan=lifespan)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(health_router)
app.include_router(settings_router)
app.include_router(mt5_router)
app.include_router(overlay_router)
app.include_router(alerts_router, prefix="/alerts")
app.include_router(notifications_router, prefix="/notifications")
app.include_router(history_router, prefix="/history")
app.include_router(awakening_router)
app.include_router(order_sync_router)
app.include_router(risk_control_router)
app.include_router(stream_router)
app.include_router(local_copy_trading_router)

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8765)
