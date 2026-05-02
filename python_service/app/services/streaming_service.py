import asyncio
from datetime import datetime
from fastapi import WebSocket
from python_service.app.services.mt5_service import get_mt5_client, get_positions
from python_service.app.services.alert_service import evaluate_alerts
from python_service.app.models.alerts import PriceAlert, VolatilityAlert, IndicatorAlert, OrderBroadcastRule
import MetaTrader5 as mt5

class WebSocketManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Handle broken connections gracefully
                pass

manager = WebSocketManager()

# Global state for monitoring
price_history: dict[str, list[dict]] = {}
MAX_HISTORY_SECONDS = 3600  # Keep 1 hour of history for volatility
seen_order_keys: set[str] = set()


def format_order_broadcast_message(order: dict, language: str) -> str:
    order_type = order.get('type')
    symbol = order.get('symbol', '')
    price = order.get('price_open') or 0
    sl = order.get('sl') or 0
    tp = order.get('tp') or 0

    if language == 'en':
        action = 'Buy' if order_type == mt5.POSITION_TYPE_BUY else 'Sell'
        return f"{action} {symbol} at {price:.2f} sl:{sl:.2f} tp:{tp:.2f}"

    action = '买' if order_type == mt5.POSITION_TYPE_BUY else '卖'
    return f"{action} {symbol} 在 {price:.2f} 止损:{sl:.2f} 止盈:{tp:.2f}"

async def streaming_loop():
    """Background task to poll MT5 and broadcast quotes/alerts."""
    while True:
        try:
            client = get_mt5_client()
            if client and mt5.terminal_info():
                # Get current prices for symbols from settings
                from python_service.app.routes.settings import get_settings
                settings = get_settings()
                symbols = settings.overlay_symbols or ["XAUUSD"]
                quotes = {}
                
                for symbol in symbols:
                    tick = mt5.symbol_info_tick(symbol)
                    info = mt5.symbol_info(symbol)
                    # Fetch daily open
                    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 1)
                    daily_open = rates[0]['open'] if rates is not None and len(rates) > 0 else None
                    
                    if tick and info:
                        change_pct = ((tick.bid - daily_open) / daily_open * 100) if daily_open and daily_open > 0 else 0
                        quotes[symbol] = {
                            "bid": tick.bid,
                            "ask": tick.ask,
                            "time": tick.time,
                            "digits": info.digits,
                            "daily_open": daily_open,
                            "change_pct": change_pct
                        }
                
                # Broadcast quote update
                if quotes:
                    await manager.broadcast({
                        "type": "quotes",
                        "data": quotes,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Update price history for volatility
                    now_ts = datetime.now().timestamp()
                    for symbol, q in quotes.items():
                        if symbol not in price_history:
                            price_history[symbol] = []
                        price_history[symbol].append({"price": q['bid'], "timestamp": now_ts})
                        # Trim old history
                        price_history[symbol] = [e for e in price_history[symbol] if now_ts - e['timestamp'] <= MAX_HISTORY_SECONDS]

                    # 1. Price Alerts
                    from python_service.app.routes.alerts import active_alerts
                    from python_service.app.services.notifier_service import notify_all
                    from python_service.app.routes.settings import get_settings
                    
                    price_rules = [a for a in active_alerts if isinstance(a, PriceAlert)]
                    if price_rules:
                        current_prices = {s: q['bid'] for s, q in quotes.items()}
                        triggered_price, messages = evaluate_alerts(price_rules, current_prices)
                        for msg in messages:
                            await notify_all("价格预警触发", msg)

                    # 2. Volatility Alerts
                    from python_service.app.services.alert_service import evaluate_volatility
                    vol_rules = [a for a in active_alerts if isinstance(a, VolatilityAlert)]
                    if vol_rules:
                        triggered_vol, messages = evaluate_volatility(vol_rules, price_history)
                        for msg in messages:
                            await notify_all("波动预警触发", msg)
                
                # Check account state too
                account = mt5.account_info()
                if account:
                    await manager.broadcast({
                        "type": "account",
                        "data": {
                            "balance": account.balance,
                            "equity": account.equity,
                            "profit": account.profit
                        }
                    })

                # Check indicator alerts
                from python_service.app.services.alert_service import evaluate_indicator_alerts
                indicator_rules = [a for a in active_alerts if isinstance(a, IndicatorAlert)]
                if indicator_rules:
                    triggered_indicators, messages = evaluate_indicator_alerts(indicator_rules)
                    for msg in messages:
                        await notify_all("指标预警触发", msg)

                order_broadcast_rules = [a for a in active_alerts if isinstance(a, OrderBroadcastRule) and a.is_active]
                if order_broadcast_rules:
                    settings = get_settings()
                    watched_symbols = {rule.symbol.upper() for rule in order_broadcast_rules}
                    for position in get_positions():
                        symbol = str(position.get('symbol', '')).upper()
                        if symbol not in watched_symbols:
                            continue

                        order_type = position.get('type')
                        if order_type not in {mt5.POSITION_TYPE_BUY, mt5.POSITION_TYPE_SELL}:
                            continue

                        key = f"{position.get('ticket')}:{position.get('time_msc') or position.get('time')}"
                        if key in seen_order_keys:
                            continue

                        seen_order_keys.add(key)
                        await notify_all(
                            "订单广播",
                            format_order_broadcast_message(position, settings.language)
                        )

            await asyncio.sleep(1.0)
        except Exception as e:
            print(f"Streaming loop error: {e}")
            await asyncio.sleep(5)
