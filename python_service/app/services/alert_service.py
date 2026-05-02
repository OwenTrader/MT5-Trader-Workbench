from python_service.app.models.alerts import PriceAlert, VolatilityAlert, IndicatorAlert
from python_service.app.services.indicator_service import get_indicator_value

# ... (existing evaluate_alerts and evaluate_volatility)

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
            messages.append(f"{alert.symbol} reached {current_price} (Target: >= {alert.price})")
        elif alert.condition == 'below' and current_price <= alert.price:
            alert.is_triggered = True
            triggered.append(alert)
            messages.append(f"{alert.symbol} reached {current_price} (Target: <= {alert.price})")
            
    return triggered, messages

def evaluate_volatility(alerts: list[VolatilityAlert], price_history: dict[str, list[dict]]) -> tuple[list[VolatilityAlert], list[str]]:
    triggered = []
    messages = []
    
    for alert in alerts:
        if not alert.is_active or alert.is_triggered:
            continue
            
        history = price_history.get(alert.symbol, [])
        if len(history) < 2:
            continue
            
        # Check moves within timeframe
        latest = history[-1]
        for entry in reversed(history[:-1]):
            # Check if entry is older than the timeframe
            if latest['timestamp'] - entry['timestamp'] > alert.timeframe_seconds:
                break
                
            # Calculation depends on symbol digits. 
            # In MT5, 1 point is the smallest price change.
            price_move = abs(latest['price'] - entry['price'])
            
            # Simple assumption: 1 point = 0.01 for XAUUSD (2 digits) or 0.00001 for FX (5 digits)
            # Better to use symbol info digits if available, but for now we calculate raw move
            # and compare with points. We'll refine this in streaming_service if needed.
            if price_move >= alert.threshold_points:
                alert.is_triggered = True
                triggered.append(alert)
                messages.append(f"Volatility Alert: {alert.symbol} moved {price_move:.5f} in {latest['timestamp'] - entry['timestamp']:.1f}s (Threshold: {alert.threshold_points})")
                break
                
    return triggered, messages
