import json
import logging
import os
import threading
import uuid

from fastapi import APIRouter, HTTPException

from python_service.app.models.alerts import IndicatorAlert, OrderBroadcastRule, PriceAlert, VolatilityAlert

router = APIRouter()

logger = logging.getLogger(__name__)

from python_service.app.services.storage_paths import alerts_file

# Mutated by the API routes (worker threads) and iterated by the streaming
# poll thread. The lock guards cross-thread access; the list itself is NEVER
# rebound so every holder of the reference sees the same object.
active_alerts: list[PriceAlert | VolatilityAlert | IndicatorAlert | OrderBroadcastRule] = []
_alerts_lock = threading.RLock()


def ensure_unique_order_broadcast_symbol(symbol: str, exclude_id: str | None = None):
    normalized_symbol = symbol.strip().upper()
    for alert in active_alerts:
        if not isinstance(alert, OrderBroadcastRule):
            continue
        if alert.id == exclude_id:
            continue
        if alert.symbol.strip().upper() == normalized_symbol:
            raise HTTPException(status_code=409, detail={'code': 'duplicate_symbol'})


def save_alerts():
    with _alerts_lock:
        alerts_file().parent.mkdir(parents=True, exist_ok=True)
        serialized = []
        for a in active_alerts:
            data = a.model_dump()
            if isinstance(a, PriceAlert):
                data['type'] = 'price'
            elif isinstance(a, VolatilityAlert):
                data['type'] = 'volatility'
            elif isinstance(a, IndicatorAlert):
                data['type'] = 'indicator'
            elif isinstance(a, OrderBroadcastRule):
                data['type'] = 'order-broadcast'
            serialized.append(data)

        with open(alerts_file(), 'w', encoding='utf-8') as f:
            json.dump(serialized, f, ensure_ascii=False, indent=2)


def load_alerts():
    if not alerts_file().exists():
        return

    try:
        with open(alerts_file(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        new_alerts = []
        for item in data:
            alert_type = item.pop('type', None)
            if alert_type != 'order-broadcast':
                item['is_active'] = False
            item['is_triggered'] = False

            if alert_type == 'price':
                new_alerts.append(PriceAlert(**item))
            elif alert_type == 'volatility':
                new_alerts.append(VolatilityAlert(**item))
            elif alert_type == 'indicator':
                new_alerts.append(IndicatorAlert(**item))
            elif alert_type == 'order-broadcast':
                new_alerts.append(OrderBroadcastRule(**item))
        with _alerts_lock:
            # In-place swap: other modules hold this exact list reference.
            active_alerts[:] = new_alerts
    except Exception:
        logger.exception('Failed to load alerts from %s', alerts_file())


# Initial load on startup
load_alerts()


def _replace_alert(index: int, updated) -> None:
    active_alerts[index] = updated


@router.get('/price')
def get_price_rules():
    with _alerts_lock:
        return [a for a in active_alerts if isinstance(a, PriceAlert)]


@router.post('/price')
def add_price_rule(alert: PriceAlert):
    if not alert.id:
        alert.id = str(uuid.uuid4())
    with _alerts_lock:
        active_alerts.append(alert)
        save_alerts()
    return {'status': 'ok', 'id': alert.id}


@router.put('/price/{id}')
def update_price_rule(id: str, updated_alert: PriceAlert):
    with _alerts_lock:
        for i, alert in enumerate(active_alerts):
            if hasattr(alert, 'id') and alert.id == id:
                updated_alert.id = id
                updated_alert.is_triggered = False  # an edited alert re-arms
                active_alerts[i] = updated_alert
                save_alerts()
                return {'status': 'ok'}
    raise HTTPException(status_code=404, detail='Alert not found')


@router.delete('/price/{id}')
def delete_price_rule(id: str):
    with _alerts_lock:
        active_alerts[:] = [a for a in active_alerts if not (hasattr(a, 'id') and a.id == id)]
        save_alerts()
    return {'status': 'ok'}


@router.get('/volatility')
def get_volatility_rules():
    with _alerts_lock:
        return [a for a in active_alerts if isinstance(a, VolatilityAlert)]


@router.post('/volatility')
def add_volatility_rule(alert: VolatilityAlert):
    if not alert.id:
        alert.id = str(uuid.uuid4())
    with _alerts_lock:
        active_alerts.append(alert)
        save_alerts()
    return {'status': 'ok', 'id': alert.id}


@router.put('/volatility/{id}')
def update_volatility_rule(id: str, updated_alert: VolatilityAlert):
    with _alerts_lock:
        for i, alert in enumerate(active_alerts):
            if hasattr(alert, 'id') and alert.id == id:
                updated_alert.id = id
                updated_alert.is_triggered = False
                active_alerts[i] = updated_alert
                save_alerts()
                return {'status': 'ok'}
    raise HTTPException(status_code=404, detail='Alert not found')


@router.delete('/volatility/{id}')
def delete_volatility_rule(id: str):
    with _alerts_lock:
        active_alerts[:] = [a for a in active_alerts if not (hasattr(a, 'id') and a.id == id)]
        save_alerts()
    return {'status': 'ok'}


# Indicator Alerts
@router.get('/indicator')
def get_indicator_rules():
    with _alerts_lock:
        return [a for a in active_alerts if isinstance(a, IndicatorAlert)]


@router.post('/indicator')
def add_indicator_rule(alert: IndicatorAlert):
    if not alert.id:
        alert.id = str(uuid.uuid4())
    with _alerts_lock:
        active_alerts.append(alert)
        save_alerts()
    return {'status': 'ok', 'id': alert.id}


@router.put('/indicator/{id}')
def update_indicator_rule(id: str, updated_alert: IndicatorAlert):
    with _alerts_lock:
        for i, alert in enumerate(active_alerts):
            if hasattr(alert, 'id') and alert.id == id:
                updated_alert.id = id
                updated_alert.is_triggered = False
                active_alerts[i] = updated_alert
                save_alerts()
                return {'status': 'ok'}
    raise HTTPException(status_code=404, detail='Alert not found')


@router.delete('/indicator/{id}')
def delete_indicator_rule(id: str):
    with _alerts_lock:
        active_alerts[:] = [a for a in active_alerts if not (hasattr(a, 'id') and a.id == id)]
        save_alerts()
    return {'status': 'ok'}


@router.get('/order-broadcast')
def get_order_broadcast_rules():
    with _alerts_lock:
        return [a for a in active_alerts if isinstance(a, OrderBroadcastRule)]


@router.post('/order-broadcast')
def add_order_broadcast_rule(rule: OrderBroadcastRule):
    with _alerts_lock:
        ensure_unique_order_broadcast_symbol(rule.symbol)
        if not rule.id:
            rule.id = str(uuid.uuid4())
        active_alerts.append(rule)
        save_alerts()
    return {'status': 'ok', 'id': rule.id}


@router.put('/order-broadcast/{id}')
def update_order_broadcast_rule(id: str, updated_rule: OrderBroadcastRule):
    with _alerts_lock:
        for i, alert in enumerate(active_alerts):
            if hasattr(alert, 'id') and alert.id == id:
                ensure_unique_order_broadcast_symbol(updated_rule.symbol, exclude_id=id)
                updated_rule.id = id
                active_alerts[i] = updated_rule
                save_alerts()
                return {'status': 'ok'}
    raise HTTPException(status_code=404, detail='Alert not found')


@router.delete('/order-broadcast/{id}')
def delete_order_broadcast_rule(id: str):
    with _alerts_lock:
        active_alerts[:] = [a for a in active_alerts if not (hasattr(a, 'id') and a.id == id)]
        save_alerts()
    return {'status': 'ok'}
