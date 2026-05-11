def append_quote_to_history(price_history: dict[str, list[dict]], symbol: str, price: float, now_ts: float) -> None:
    if symbol not in price_history:
        price_history[symbol] = []
    price_history[symbol].append({'price': price, 'timestamp': now_ts})


def trim_price_history(price_history: dict[str, list[dict]], now_ts: float, max_history_seconds: int) -> None:
    for symbol, entries in price_history.items():
        price_history[symbol] = [entry for entry in entries if now_ts - entry['timestamp'] <= max_history_seconds]
