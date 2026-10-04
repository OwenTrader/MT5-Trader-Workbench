from fastapi import APIRouter

from python_service.app.services import loop_heartbeat

router = APIRouter()


@router.get('/health')
def health() -> dict:
    # Loop heartbeats make a silently dead background task visible: a loop
    # missing from the map has never ticked, a growing age means it died.
    return {
        'status': 'ok',
        'loops': loop_heartbeat.snapshot(),
    }
