import uuid
import json
import os
from fastapi import APIRouter, HTTPException
from python_service.app.models.alerts import PriceAlert, VolatilityAlert, IndicatorAlert, OrderBroadcastRule

router = APIRouter()

# Global list of active alerts
active_alerts: list[PriceAlert | VolatilityAlert | IndicatorAlert | OrderBroadcastRule] = []
ALERTS_FILE = 'storage/alerts.json'


def ensure_unique_order_broadcast_symbol(symbol: str, exclude_id: str | None = None):
    normalized_symbol = symbol.strip().upper()
    for alert in active_alerts:
        if not isinstance(alert, OrderBroadcastRule):
            continue
        if alert.id == exclude_id:
            continue
        if alert.symbol.strip().upper() == normalized_symbol:
            raise HTTPException(status_code=409, detail={"code": "duplicate_symbol"})

def save_alerts():
    os.makedirs('storage', exist_ok=True)
    serialized = []
    for a in active_alerts:
        data = a.model_dump()
        if isinstance(a, PriceAlert): data['type'] = 'price'
        elif isinstance(a, VolatilityAlert): data['type'] = 'volatility'
        elif isinstance(a, IndicatorAlert): data['type'] = 'indicator'
        elif isinstance(a, OrderBroadcastRule): data['type'] = 'order-broadcast'
        serialized.append(data)
    
    with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(serialized, f, ensure_ascii=False, indent=2)

def load_alerts():
    global active_alerts
    if not os.path.exists(ALERTS_FILE):
        return
    
    try:
        with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
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
            active_alerts = new_alerts
    except Exception as e:
        print(f"Failed to load alerts: {e}")

# Initial load on startup
load_alerts()

@router.get("/price")
async def get_price_rules():
    return [a for a in active_alerts if isinstance(a, PriceAlert)]

@router.post("/price")
async def add_price_rule(alert: PriceAlert):
    if not alert.id:
        alert.id = str(uuid.uuid4())
    active_alerts.append(alert)
    save_alerts()
    return {"status": "ok", "id": alert.id}

@router.get("/volatility")
async def get_volatility_rules():
    return [a for a in active_alerts if isinstance(a, VolatilityAlert)]

@router.post("/volatility")
async def add_volatility_rule(alert: VolatilityAlert):
    if not alert.id:
        alert.id = str(uuid.uuid4())
    active_alerts.append(alert)
    save_alerts()
    return {"status": "ok", "id": alert.id}

@router.put("/price/{id}")
async def update_price_rule(id: str, updated_alert: PriceAlert):
    global active_alerts
    for i, alert in enumerate(active_alerts):
        if hasattr(alert, 'id') and alert.id == id:
            active_alerts[i] = updated_alert
            save_alerts()
            return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Alert not found")

@router.delete("/price/{id}")
async def delete_price_rule(id: str):
    global active_alerts
    active_alerts = [a for a in active_alerts if not (hasattr(a, 'id') and a.id == id)]
    save_alerts()
    return {"status": "ok"}

@router.put("/volatility/{id}")
async def update_volatility_rule(id: str, updated_alert: VolatilityAlert):
    global active_alerts
    for i, alert in enumerate(active_alerts):
        if hasattr(alert, 'id') and alert.id == id:
            active_alerts[i] = updated_alert
            save_alerts()
            return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Alert not found")

@router.delete("/volatility/{id}")
async def delete_volatility_rule(id: str):
    global active_alerts
    active_alerts = [a for a in active_alerts if not (hasattr(a, 'id') and a.id == id)]
    save_alerts()
    return {"status": "ok"}

# Indicator Alerts
@router.get("/indicator")
async def get_indicator_rules():
    return [a for a in active_alerts if isinstance(a, IndicatorAlert)]

@router.post("/indicator")
async def add_indicator_rule(alert: IndicatorAlert):
    if not alert.id:
        alert.id = str(uuid.uuid4())
    active_alerts.append(alert)
    save_alerts()
    return {"status": "ok", "id": alert.id}

@router.put("/indicator/{id}")
async def update_indicator_rule(id: str, updated_alert: IndicatorAlert):
    global active_alerts
    for i, alert in enumerate(active_alerts):
        if hasattr(alert, 'id') and alert.id == id:
            active_alerts[i] = updated_alert
            save_alerts()
            return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Alert not found")

@router.delete("/indicator/{id}")
async def delete_indicator_rule(id: str):
    global active_alerts
    active_alerts = [a for a in active_alerts if not (hasattr(a, 'id') and a.id == id)]
    save_alerts()
    return {"status": "ok"}


@router.get("/order-broadcast")
async def get_order_broadcast_rules():
    return [a for a in active_alerts if isinstance(a, OrderBroadcastRule)]


@router.post("/order-broadcast")
async def add_order_broadcast_rule(rule: OrderBroadcastRule):
    ensure_unique_order_broadcast_symbol(rule.symbol)
    if not rule.id:
        rule.id = str(uuid.uuid4())
    active_alerts.append(rule)
    save_alerts()
    return {"status": "ok", "id": rule.id}


@router.put("/order-broadcast/{id}")
async def update_order_broadcast_rule(id: str, updated_rule: OrderBroadcastRule):
    global active_alerts
    for i, alert in enumerate(active_alerts):
        if hasattr(alert, 'id') and alert.id == id:
            ensure_unique_order_broadcast_symbol(updated_rule.symbol, exclude_id=id)
            updated_rule.id = id
            active_alerts[i] = updated_rule
            save_alerts()
            return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Alert not found")


@router.delete("/order-broadcast/{id}")
async def delete_order_broadcast_rule(id: str):
    global active_alerts
    active_alerts = [a for a in active_alerts if not (hasattr(a, 'id') and a.id == id)]
    save_alerts()
    return {"status": "ok"}
