from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from contextlib import asynccontextmanager

from python_service.app.routes.health import router as health_router
from python_service.app.routes.settings import router as settings_router
from python_service.app.routes.mt5 import router as mt5_router
from python_service.app.routes.overlay import router as overlay_router
from python_service.app.routes.alerts import router as alerts_router
from python_service.app.routes.stream import router as stream_router
from python_service.app.routes.notifications import router as notifications_router
from python_service.app.routes.history import router as history_router
from python_service.app.routes.awakening import router as awakening_router
from python_service.app.services.streaming_service import streaming_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    asyncio.create_task(streaming_loop())
    yield
    # Shutdown logic (if any)

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
app.include_router(stream_router)

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8765)
