import asyncio
from datetime import datetime
from fastapi import WebSocket
from python_service.app.services.mt5_service import get_mt5_client, get_positions, mt5_connection_lock
from python_service.app.services.alert_dispatch_service import dispatch_price_alerts
from python_service.app.services.quote_snapshot_service import append_quote_to_history, trim_price_history
from python_service.app.models.alerts import PriceAlert, VolatilityAlert, IndicatorAlert, OrderBroadcastRule
from python_service.app.routes.settings import get_settings
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
order_broadcast_snapshots: dict[str, dict] = {}


ORDER_ACTIONS = {
    getattr(mt5, 'POSITION_TYPE_BUY', 0): 'buy',
    getattr(mt5, 'POSITION_TYPE_SELL', 1): 'sell',
    getattr(mt5, 'ORDER_TYPE_BUY', 0): 'buy',
    getattr(mt5, 'ORDER_TYPE_SELL', 1): 'sell',
    getattr(mt5, 'ORDER_TYPE_BUY_LIMIT', 2): 'buy limit',
    getattr(mt5, 'ORDER_TYPE_SELL_LIMIT', 3): 'sell limit',
    getattr(mt5, 'ORDER_TYPE_BUY_STOP', 4): 'buy stop',
    getattr(mt5, 'ORDER_TYPE_SELL_STOP', 5): 'sell stop',
    getattr(mt5, 'ORDER_TYPE_BUY_STOP_LIMIT', 6): 'buy stop limit',
    getattr(mt5, 'ORDER_TYPE_SELL_STOP_LIMIT', 7): 'sell stop limit',
}


def should_poll_mt5() -> bool:
    if manager.active_connections:
        return True

    try:
        if get_settings().auto_connect:
            return True

        from python_service.app.routes.alerts import active_alerts
        return any(isinstance(alert, OrderBroadcastRule) and alert.is_active for alert in active_alerts)
    except Exception:
        return False


def _format_number(value: float | int | None) -> str:
    numeric_value = float(value or 0)
    return f"{numeric_value:.5f}".rstrip('0').rstrip('.')


def _format_order_base(order: dict) -> str:
    order_type = order.get('type')
    symbol = str(order.get('symbol', '')).upper()
    action = ORDER_ACTIONS.get(order_type, str(order_type).lower())
    volume = order.get('volume') or order.get('volume_current') or order.get('volume_initial') or 0
    price = order.get('price_open') or order.get('price_current') or order.get('price_stoplimit') or 0
    tp = order.get('tp') or 0
    sl = order.get('sl') or 0
    return f"{symbol} {action} {_format_number(volume)} at {_format_number(price)},tp:{_format_number(tp)},sl:{_format_number(sl)}"


def format_order_broadcast_message(order: dict, language: str | None = None) -> str:
    return _format_order_base(order)


def format_order_modified_message(previous: dict, current: dict) -> str | None:
    changes = []
    for field, label in [('price_open', 'price'), ('tp', 'tp'), ('sl', 'sl')]:
        if previous.get(field) != current.get(field):
            changes.append(f"modify {label} to {_format_number(current.get(field))}")

    previous_volume = previous.get('volume') or previous.get('volume_current') or previous.get('volume_initial') or 0
    current_volume = current.get('volume') or current.get('volume_current') or current.get('volume_initial') or 0
    if previous_volume != current_volume:
        changes.append(f"modify volume to {_format_number(current_volume)}")

    if not changes:
        return None

    return f"{_format_order_base(current)}. {', '.join(changes)}"


def format_order_cancelled_message(order: dict) -> str:
    return f"{_format_order_base(order)}. canceled"


def _as_dicts(values) -> list[dict] | None:
    if values is None:
        return None
    if not values:
        return []
    return [value._asdict() if hasattr(value, '_asdict') else dict(value) for value in values]


def get_current_order_broadcast_items() -> list[dict] | None:
    try:
        positions = _as_dicts(mt5.positions_get())
        pending_orders = _as_dicts(mt5.orders_get())
    except Exception as exc:
        print(f"Order broadcast skipped: failed to read MT5 orders, error={exc}")
        return None

    if positions is None or pending_orders is None:
        print(f"Order broadcast skipped: MT5 returned no order data, error={mt5.last_error()}")
        return None

    return [
        *({**position, 'source': 'position'} for position in positions),
        *({**order, 'source': 'order'} for order in pending_orders),
    ]


def _order_snapshot_key(order: dict) -> str:
    return f"{order.get('source', 'order')}:{order.get('ticket')}"


def _normalize_order_snapshot(order: dict) -> dict:
    return {
        'source': order.get('source', 'order'),
        'ticket': order.get('ticket'),
        'symbol': str(order.get('symbol', '')).upper(),
        'type': order.get('type'),
        'volume': order.get('volume') or order.get('volume_current') or order.get('volume_initial') or 0,
        'price_open': order.get('price_open') or order.get('price_current') or order.get('price_stoplimit') or 0,
        'tp': order.get('tp') or 0,
        'sl': order.get('sl') or 0,
    }


def collect_order_broadcast_messages(orders: list[dict], watched_symbols: set[str]) -> list[str]:
    global order_broadcast_snapshots

    current_snapshots = {}
    messages = []

    for order in orders:
        snapshot = _normalize_order_snapshot(order)
        if not snapshot['ticket'] or snapshot['symbol'] not in watched_symbols:
            continue

        key = _order_snapshot_key(snapshot)
        current_snapshots[key] = snapshot
        previous = order_broadcast_snapshots.get(key)

        if previous is None:
            messages.append(format_order_broadcast_message(snapshot))
            continue

        modified_message = format_order_modified_message(previous, snapshot)
        if modified_message:
            messages.append(modified_message)

    for key, previous in order_broadcast_snapshots.items():
        if previous.get('symbol') in watched_symbols and key not in current_snapshots:
            messages.append(format_order_cancelled_message(previous))

    order_broadcast_snapshots = current_snapshots
    return messages


def _read_symbol_quote(symbol: str) -> dict | None:
    if not mt5.symbol_select(symbol, True):
        print(f"Quote skipped: failed to select symbol {symbol}, error={mt5.last_error()}")
        return None

    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if not tick or not info:
        print(f"Quote skipped: missing tick/info for {symbol}, error={mt5.last_error()}")
        return None

    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 1)
    daily_open = rates[0]['open'] if rates is not None and len(rates) > 0 else None
    change_pct = ((tick.bid - daily_open) / daily_open * 100) if daily_open and daily_open > 0 else 0

    return {
        "bid": tick.bid,
        "ask": tick.ask,
        "time": tick.time,
        "digits": info.digits,
        "daily_open": daily_open,
        "change_pct": change_pct
    }


def _find_matching_symbol(symbol: str) -> str | None:
    try:
        matches = mt5.symbols_get(f"{symbol}*") or []
    except Exception as exc:
        print(f"Quote skipped: failed to search symbols for {symbol}, error={exc}")
        return None

    for match in matches:
        name = getattr(match, 'name', '')
        if name.upper().startswith(symbol):
            return name

    return None


def get_symbol_quote(symbol: str) -> dict | None:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        return None

    quote = _read_symbol_quote(normalized_symbol)
    if quote:
        return quote

    matched_symbol = _find_matching_symbol(normalized_symbol)
    if matched_symbol and matched_symbol.upper() != normalized_symbol:
        return _read_symbol_quote(matched_symbol)

    return None


def get_symbol_quotes(symbols: list[str]) -> dict[str, dict]:
    quotes = {}
    for symbol in symbols:
        quote = get_symbol_quote(symbol)
        if quote:
            quotes[symbol.strip().upper()] = quote
    return quotes


async def streaming_loop():
    """Background task to poll MT5 and broadcast quotes/alerts."""
    while True:
        try:
            if not should_poll_mt5():
                await asyncio.sleep(1.0)
                continue

            quote_broadcast = None
            account_broadcast = None
            price_rules = []
            current_prices = {}
            notifications: list[tuple[str, str]] = []
            client_available = False

            with mt5_connection_lock():
                client = get_mt5_client(allow_launch=False)
                client_available = bool(client and mt5.terminal_info())
                if not client_available:
                    pass
                else:
                    settings = get_settings()
                    from python_service.app.routes.alerts import active_alerts
                    symbols = settings.overlay_symbols or ["XAUUSD"]
                    quotes = get_symbol_quotes(symbols)

                    if quotes:
                        quote_broadcast = {
                            "type": "quotes",
                            "data": quotes,
                            "timestamp": datetime.now().isoformat()
                        }

                        now_ts = datetime.now().timestamp()
                        for symbol, q in quotes.items():
                            append_quote_to_history(price_history, symbol, q['bid'], now_ts)
                        trim_price_history(price_history, now_ts, MAX_HISTORY_SECONDS)

                        price_rules = [a for a in active_alerts if isinstance(a, PriceAlert)]
                        current_prices = {s: q['bid'] for s, q in quotes.items()}

                        from python_service.app.services.alert_service import evaluate_volatility
                        vol_rules = [a for a in active_alerts if isinstance(a, VolatilityAlert)]
                        if vol_rules:
                            triggered_vol, messages = evaluate_volatility(vol_rules, price_history)
                            notifications.extend(("波动预警触发", message) for message in messages)

                    account = mt5.account_info()
                    if account:
                        account_broadcast = {
                            "type": "account",
                            "data": {
                                "balance": account.balance,
                                "equity": account.equity,
                                "profit": account.profit
                            }
                        }

                    from python_service.app.services.alert_service import evaluate_indicator_alerts
                    indicator_rules = [a for a in active_alerts if isinstance(a, IndicatorAlert)]
                    if indicator_rules:
                        triggered_indicators, messages = evaluate_indicator_alerts(indicator_rules)
                        notifications.extend(("指标预警触发", message) for message in messages)

                    order_broadcast_rules = [a for a in active_alerts if isinstance(a, OrderBroadcastRule) and a.is_active]
                    if order_broadcast_rules:
                        watched_symbols = {rule.symbol.upper() for rule in order_broadcast_rules}
                        order_broadcast_items = get_current_order_broadcast_items()
                        if order_broadcast_items is not None:
                            notifications.extend(("订单广播", message) for message in collect_order_broadcast_messages(order_broadcast_items, watched_symbols))
                    else:
                        order_broadcast_snapshots.clear()

            if not client_available:
                await asyncio.sleep(1.0)
                continue

            from python_service.app.services.notifier_service import notify_all
            if quote_broadcast:
                await manager.broadcast(quote_broadcast)
            if price_rules:
                await dispatch_price_alerts(price_rules, current_prices)
            if account_broadcast:
                await manager.broadcast(account_broadcast)
            for title, message in notifications:
                await notify_all(title, message)

            await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Streaming loop error: {e}")
            await asyncio.sleep(5)
