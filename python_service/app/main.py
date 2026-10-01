from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import uvicorn
import asyncio
import os
import subprocess
import ctypes
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
from python_service.app.routes.data_management import router as data_management_router
from python_service.app.routes.trading_review import router as trading_review_router
from python_service.app.local_copy_trading.routes import router as local_copy_trading_router
from python_service.app.quant.backtest_routes import router as python_quant_backtest_router
from python_service.app.quant.routes import router as python_quant_router
from python_service.app.services.mt5_service import shutdown_mt5, get_mt5_client
from python_service.app.services.order_sync_service import order_sync_loop
from python_service.app.services.streaming_service import streaming_loop
from python_service.app.local_copy_trading.loop import local_copy_trading_loop
from python_service.app.local_copy_trading.runtime import set_state as set_local_copy_trading_state
from python_service.app.local_copy_trading.storage import load_state as load_local_copy_trading_state
from python_service.app.quant.loop import quant_loop

PARENT_CHECK_INTERVAL_SECONDS = 2.0


def create_hidden_startupinfo():
    if os.name != 'nt':
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo


def get_parent_pid_from_env() -> int | None:
    raw_value = os.environ.get('PARENT_PID', '').strip()
    if not raw_value:
        return None
    try:
        parent_pid = int(raw_value)
    except ValueError:
        return None
    return parent_pid if parent_pid > 0 else None


def is_parent_process_alive(parent_pid: int) -> bool:
    """Check whether the Electron parent process is still running.

    Avoids spawning ``tasklist`` (which enumerates every process and stalls
    the event loop); uses a lightweight kernel handle query on Windows and a
    no-op signal on POSIX instead.
    """
    if parent_pid <= 0:
        return False

    if os.name == 'nt':
        try:
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        except AttributeError:
            return False
        PROCESS_QUERY_INFORMATION = 0x0400
        process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, parent_pid)
        if process in (0, None):
            return False
        try:
            exit_code = ctypes.c_ulong()
            if kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
                # 259 == STILL_ACTIVE
                return exit_code.value == 259
            return False
        finally:
            kernel32.CloseHandle(process)

    try:
        os.kill(parent_pid, 0)
    except OSError:
        return False
    return True


def exit_backend_process(code: int = 0) -> None:
    os._exit(code)


async def parent_process_watchdog(parent_pid: int, interval_seconds: float = PARENT_CHECK_INTERVAL_SECONDS) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        # Run the (cheap) process check off the event loop to keep it free.
        if await asyncio.to_thread(is_parent_process_alive, parent_pid):
            continue
        print(f'Parent process {parent_pid} is gone, shutting down backend.')
        shutdown_mt5()
        exit_backend_process(0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    set_local_copy_trading_state(load_local_copy_trading_state())
    background_tasks = [
        asyncio.create_task(streaming_loop()),
        asyncio.create_task(order_sync_loop()),
        asyncio.create_task(local_copy_trading_loop()),
        asyncio.create_task(quant_loop()),
    ]
    parent_pid = get_parent_pid_from_env()
    if parent_pid is not None:
        background_tasks.append(asyncio.create_task(parent_process_watchdog(parent_pid)))
        
    # Attempt to pre-launch MT5 if a path is configured in settings
    try:
        get_mt5_client(allow_launch=True)
    except Exception as e:
        print(f"Failed to eagerly launch MT5 during startup: {e}")
        
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


# CORS: strict origin allowlist. The local trading API must not be reachable from
# arbitrary web pages (a malicious site could read accounts/positions or place
# orders). The Electron renderer is either a file:// origin (packaged, Origin:
# "null") or http://localhost/127.0.0.1 (dev). Anything else is rejected.
_DEV_CORS_ORIGIN = os.environ.get('ALLOWED_CORS_ORIGIN')


def _is_allowed_origin(origin: str | None) -> bool:
    if origin is None or origin == 'null':
        return True
    if _DEV_CORS_ORIGIN and origin == _DEV_CORS_ORIGIN:
        return True
    return origin.startswith(('http://localhost:', 'http://127.0.0.1:'))


@app.middleware('http')
async def origin_guard(request: Request, call_next):
    origin = request.headers.get('origin')
    if request.method == 'OPTIONS':
        response: Response = Response()
        if _is_allowed_origin(origin):
            response.headers['Access-Control-Allow-Origin'] = origin or 'null'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = '*'
        return response
    # A browser always sends Origin on cross-site fetches; a disallowed one
    # means a foreign web page is calling the local trading API. Omitting the
    # CORS headers is not enough -- the request body would still execute --
    # so it is rejected outright. Requests without Origin (Electron file://,
    # curl, health probes) keep working as before.
    if origin is not None and not _is_allowed_origin(origin):
        return JSONResponse({'detail': 'Origin not allowed'}, status_code=403)
    response = await call_next(request)
    if _is_allowed_origin(origin):
        response.headers['Access-Control-Allow-Origin'] = origin or 'null'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = '*'
    return response


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
app.include_router(data_management_router)
app.include_router(trading_review_router)
app.include_router(local_copy_trading_router)
app.include_router(python_quant_router)
app.include_router(python_quant_backtest_router)

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8765)
