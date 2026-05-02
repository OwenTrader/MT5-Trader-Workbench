from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from python_service.app.services.streaming_service import manager

router = APIRouter()

@router.websocket("/ws/overlay")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We mostly broadcast, but can receive pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
