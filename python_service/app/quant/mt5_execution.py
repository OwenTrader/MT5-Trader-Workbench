from python_service.app.services.mt5_service import close_open_positions, place_market_order


def execute_signal(account: dict, symbol: str, lot: float, signal: str) -> None:
    normalized_signal = signal.strip().casefold()
    if normalized_signal == 'hold':
        return
    if lot <= 0:
        raise ValueError('lot must be greater than 0')

    if normalized_signal == 'close':
        close_open_positions(
            path=account.get('terminal_path', ''),
            login=account.get('login', ''),
            password=account.get('password', ''),
            server=account.get('server', ''),
            symbol=symbol,
        )
        return

    if normalized_signal not in {'buy', 'sell'}:
        raise ValueError(f'Unsupported signal: {signal}')

    place_market_order(
        path=account.get('terminal_path', ''),
        login=account.get('login', ''),
        password=account.get('password', ''),
        server=account.get('server', ''),
        symbol=symbol,
        lot=lot,
        side=normalized_signal,
    )
