from python_service.app.models.alerts import PriceAlert, VolatilityAlert, IndicatorAlert
from python_service.app.services.indicator_service import get_indicator_value

# ... (existing evaluate_alerts and evaluate_volatility)

def _append_comment(message: str, comment: str) -> str:
    trimmed_comment = comment.strip()
    if not trimmed_comment:
        return message

    return f"{message}\n备注: {trimmed_comment}"

def evaluate_indicator_alerts(alerts: list[IndicatorAlert]) -> tuple[list[IndicatorAlert], list[str]]:
    triggered = []
    messages = []
    
    for alert in alerts:
        if not alert.is_active or alert.is_triggered:
            continue
            
        value = get_indicator_value(alert.symbol, alert.timeframe, alert.indicator_type, alert.period)
        if value is None:
            continue
            
        if alert.condition == 'above' and value >= alert.threshold:
            alert.is_triggered = True
            triggered.append(alert)
            messages.append(f"Indicator Alert: {alert.symbol} {alert.indicator_type}({alert.period}) reached {value:.2f} (Target: >= {alert.threshold})")
        elif alert.condition == 'below' and value <= alert.threshold:
            alert.is_triggered = True
            triggered.append(alert)
            messages.append(f"Indicator Alert: {alert.symbol} {alert.indicator_type}({alert.period}) reached {value:.2f} (Target: <= {alert.threshold})")
            
    return triggered, messages

def evaluate_alerts(alerts: list[PriceAlert], prices: dict[str, float]) -> tuple[list[PriceAlert], list[str]]:
    triggered = []
    messages = []
    
    for alert in alerts:
        if not alert.is_active or alert.is_triggered:
            continue
            
        current_price = prices.get(alert.symbol)
        if current_price is None:
            continue
            
        if alert.condition == 'above' and current_price >= alert.price:
            alert.is_triggered = True
            triggered.append(alert)
            messages.append(_append_comment(f"{alert.symbol} reached {current_price} (Target: >= {alert.price})", alert.comment))
        elif alert.condition == 'below' and current_price <= alert.price:
            alert.is_triggered = True
            triggered.append(alert)
            messages.append(_append_comment(f"{alert.symbol} reached {current_price} (Target: <= {alert.price})", alert.comment))
            
    return triggered, messages

def _point_size(symbol: str) -> float:
    """Smallest quoted price change for the symbol, used to convert a raw
    price move into "points".

    Prefers the terminal's symbol_info; falls back to the common conventions
    (XAU-style metals quote with 2 digits, JPY pairs with 3, other FX with 5)
    so the unit conversion keeps working when MT5 is offline.
    """
    try:
        from python_service.app.services.mt5_service import mt5

        info = mt5.symbol_info(symbol)
        if info is not None:
            point = float(getattr(info, 'point', 0) or 0)
            if point > 0:
                return point
    except Exception:
        pass

    upper = symbol.upper()
    if 'XAU' in upper or 'GOLD' in upper:
        return 0.01
    if upper.endswith('JPY'):
        return 0.001
    return 0.00001


def evaluate_volatility(alerts: list[VolatilityAlert], price_history: dict[str, list[dict]]) -> tuple[list[VolatilityAlert], list[str]]:
    triggered = []
    messages = []
    
    for alert in alerts:
        if not alert.is_active or alert.is_triggered:
            continue

        history = price_history.get(alert.symbol, [])
        if len(history) < 2:
            continue

        point = _point_size(alert.symbol)

        # Check moves within timeframe
        latest = history[-1]
        for entry in reversed(history[:-1]):
            # Check if entry is older than the timeframe
            if latest['timestamp'] - entry['timestamp'] > alert.timeframe_seconds:
                break

            # threshold_points is in points: convert the raw price move to
            # the same unit before comparing (XAUUSD "100 points" is $1.00,
            # not $100).
            price_move = abs(latest['price'] - entry['price'])
            move_points = price_move / point

            if move_points >= alert.threshold_points:
                alert.is_triggered = True
                triggered.append(alert)
                messages.append(
                    f"Volatility Alert: {alert.symbol} moved {move_points:.1f} points in "
                    f"{latest['timestamp'] - entry['timestamp']:.1f}s (Threshold: {alert.threshold_points})"
                )
                break

    return triggered, messages
