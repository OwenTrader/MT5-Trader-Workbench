import asyncio
import json
import math
import os
import uuid
from datetime import datetime, timezone

from python_service.app.models.order_sync import OrderSyncConfigUpdate, OrderSyncState, OrderSymbolMapping, SyncedOrder
from python_service.app.services.mt5_service import get_positions
from python_service.app.services.topstep_service import TopStepApiError, TopStepClient


ORDER_SYNC_FILE = 'storage/order_sync.json'
_state = OrderSyncState()
_loaded = False
_clients: dict[str, TopStepClient] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_loaded() -> None:
    global _loaded, _state
    if _loaded:
        return
    _loaded = True
    if not os.path.exists(ORDER_SYNC_FILE):
        return
    try:
        with open(ORDER_SYNC_FILE, 'r', encoding='utf-8') as file:
            _state = OrderSyncState(**json.load(file))
    except Exception as exc:
        _state.last_error = f'Failed to load order sync config: {exc}'


def _save() -> None:
    os.makedirs('storage', exist_ok=True)
    with open(ORDER_SYNC_FILE, 'w', encoding='utf-8') as file:
        json.dump(_state.model_dump(), file, ensure_ascii=False, indent=2)


def get_order_sync_state() -> OrderSyncState:
    _ensure_loaded()
    return _state


def save_order_sync_config(update: OrderSyncConfigUpdate) -> OrderSyncState:
    _ensure_loaded()
    existing_orders = _state.synced_orders
    _state.enabled = update.enabled
    _state.poll_interval_seconds = max(update.poll_interval_seconds, 0.5)
    _state.block_high_frequency_orders = update.block_high_frequency_orders
    _state.high_frequency_window_seconds = max(update.high_frequency_window_seconds, 1)
    _state.credentials = update.credentials
    _state.mappings = update.mappings
    _state.synced_orders = existing_orders

    for credential in _state.credentials:
        if not credential.id:
            credential.id = str(uuid.uuid4())
    for mapping in _state.mappings:
        if not mapping.id:
            mapping.id = str(uuid.uuid4())

    _clients.clear()
    _save()
    return _state


def _get_client(credential_id: str) -> TopStepClient | None:
    credential = next((item for item in _state.credentials if item.id == credential_id and item.is_active), None)
    if not credential:
        return None
    if credential_id not in _clients:
        _clients[credential_id] = TopStepClient(credential)
    return _clients[credential_id]


def _position_ticket(position: dict) -> int | None:
    ticket = position.get('ticket') or position.get('identifier')
    return int(ticket) if ticket is not None else None


def _position_side(position: dict) -> str | None:
    position_type = position.get('type')
    if position_type == 0:
        return 'buy'
    if position_type == 1:
        return 'sell'
    return None


def calculate_topstep_contract_size(position: dict, mapping: OrderSymbolMapping) -> int:
    volume = float(position.get('volume') or 0)
    if (
        'mt5_lots' not in mapping.model_fields_set
        and 'topstep_contracts' not in mapping.model_fields_set
        and float(mapping.quantity_multiplier or 1) != 1
    ):
        return max(1, math.floor(volume * float(mapping.quantity_multiplier) + 0.000001))

    mt5_lots = max(float(mapping.mt5_lots or 1), 0.000001)
    topstep_contracts = max(int(mapping.topstep_contracts or 1), 1)
    return max(1, math.floor((volume / mt5_lots) * topstep_contracts + 0.000001))


async def run_topstep_with_retries(operation, attempts: int = 3, retry_delay_seconds: float = 0.5):
    last_error: TopStepApiError | None = None
    for attempt in range(attempts):
        try:
            return await asyncio.to_thread(operation)
        except TopStepApiError as exc:
            last_error = exc
            if attempt < attempts - 1 and retry_delay_seconds > 0:
                await asyncio.sleep(retry_delay_seconds)
    if last_error:
        raise last_error
    return None


def should_block_high_frequency_order(state: OrderSyncState, symbol: str, side: str, mt5_volume: float, now_iso: str) -> bool:
    if not state.block_high_frequency_orders:
        return False

    now = datetime.fromisoformat(now_iso)
    for order in state.synced_orders:
        if order.status not in {'open', 'closed'}:
            continue
        if order.mt5_symbol != symbol or order.side != side:
            continue
        if abs(float(order.mt5_volume or 0) - mt5_volume) > 0.000001:
            continue
        opened_at = datetime.fromisoformat(order.opened_at)
        if (now - opened_at).total_seconds() <= state.high_frequency_window_seconds:
            return True
    return False


def reset_order_sync_state_for_tests(state: OrderSyncState | None = None) -> None:
    global _state, _loaded, _clients
    _state = state or OrderSyncState()
    _loaded = True
    _clients = {}


async def process_order_sync_tick() -> None:
    _ensure_loaded()
    _state.last_checked_at = _utc_now()
    if not _state.enabled:
        _save()
        return

    active_credentials = [credential for credential in _state.credentials if credential.is_active]
    if not active_credentials:
        _state.last_error = 'No active TopStep credential configured'
        _save()
        return

    positions = get_positions()
    active_tickets = {_position_ticket(position) for position in positions}
    active_tickets.discard(None)
    open_synced_orders = [order for order in _state.synced_orders if order.status == 'open']

    for order in open_synced_orders:
        if order.mt5_ticket in active_tickets:
            continue
        credential = next((item for item in active_credentials if item.account_id == order.topstep_account_id), None)
        if not credential:
            order.last_error = 'TopStep credential for synced order is no longer active'
            continue
        try:
            client = _get_client(credential.id)
            if client:
                await run_topstep_with_retries(lambda: client.close_contract_position(order.topstep_contract_id))
            order.status = 'closed'
            order.closed_at = _utc_now()
            order.last_error = None
        except TopStepApiError as exc:
            order.last_error = str(exc)
            _state.last_error = str(exc)

    already_synced = {
        order.mt5_ticket
        for order in _state.synced_orders
        if order.mt5_ticket in active_tickets and order.status in {'open', 'blocked'}
    }
    for position in positions:
        ticket = _position_ticket(position)
        symbol = str(position.get('symbol') or '').strip().upper()
        side = _position_side(position)
        if ticket is None or ticket in already_synced or side is None:
            continue

        mapping = next((item for item in _state.mappings if item.is_active and item.mt5_symbol == symbol), None)
        if not mapping:
            continue

        credential = active_credentials[0]
        now_iso = _utc_now()
        mt5_volume = float(position.get('volume') or 0)
        if should_block_high_frequency_order(_state, symbol, side, mt5_volume, now_iso):
            _state.synced_orders.append(SyncedOrder(
                mt5_ticket=ticket,
                mt5_symbol=symbol,
                mt5_volume=mt5_volume,
                topstep_account_id=credential.account_id,
                topstep_contract_id=mapping.topstep_contract_id,
                side=side,
                size=0,
                status='blocked',
                opened_at=now_iso,
                blocked_reason='high_frequency_duplicate',
            ))
            continue

        size = calculate_topstep_contract_size(position, mapping)
        synced_order = SyncedOrder(
            mt5_ticket=ticket,
            mt5_symbol=symbol,
            mt5_volume=mt5_volume,
            topstep_account_id=credential.account_id,
            topstep_contract_id=mapping.topstep_contract_id,
            side=side,
            size=size,
            opened_at=now_iso,
        )
        try:
            client = _get_client(credential.id)
            if client:
                order_id = await run_topstep_with_retries(
                    lambda: client.place_market_order(
                        mapping.topstep_contract_id,
                        side,
                        size,
                        f'mt5-{ticket}',
                    )
                )
                synced_order.topstep_order_id = order_id
            synced_order.last_error = None
        except TopStepApiError as exc:
            synced_order.status = 'error'
            synced_order.last_error = str(exc)
            _state.last_error = str(exc)
        _state.synced_orders.append(synced_order)

    _save()


async def order_sync_loop() -> None:
    while True:
        try:
            await process_order_sync_tick()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _state.last_error = str(exc)
            _save()
        await asyncio.sleep(max(_state.poll_interval_seconds, 0.5))
