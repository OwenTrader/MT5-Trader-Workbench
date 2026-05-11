from fastapi import APIRouter

from python_service.app.models.order_sync import OrderSyncConfigUpdate, OrderSyncState
from python_service.app.services.order_sync_service import get_order_sync_state, process_order_sync_tick, save_order_sync_config


router = APIRouter(prefix='/order-sync')


@router.get('')
def get_order_sync() -> OrderSyncState:
    return get_order_sync_state()


@router.post('')
def save_order_sync(update: OrderSyncConfigUpdate) -> OrderSyncState:
    return save_order_sync_config(update)


@router.post('/tick')
async def run_order_sync_tick() -> OrderSyncState:
    await process_order_sync_tick()
    return get_order_sync_state()
