from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from python_service.app.services.origin import is_allowed_origin
from python_service.app.services.streaming_service import manager

router = APIRouter()


@router.websocket('/ws/overlay')
async def websocket_endpoint(websocket: WebSocket):
    # The HTTP origin-guard middleware does not cover WebSockets, so foreign
    # pages could otherwise subscribe to the account/positions broadcast.
    if not is_allowed_origin(websocket.headers.get('origin')):
        await websocket.close(code=1008)
        return

    await manager.connect(websocket)
    try:
        while True:
            # We mostly broadcast, but can receive pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
