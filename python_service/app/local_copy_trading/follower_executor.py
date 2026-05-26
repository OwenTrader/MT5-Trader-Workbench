import math

from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount
from python_service.app.local_copy_trading.models import SyncEvent
from python_service.app.services.mt5_service import init_mt5_account, mt5, mt5_connection_lock, shutdown_mt5


def _position_is_buy(position: dict) -> bool:
    value = position.get('type')
    if isinstance(value, str):
        return value.strip().casefold() in {'buy', 'long', '0'}
    return int(value or 0) == getattr(mt5, 'POSITION_TYPE_BUY', 0)


def _normalize_volume(raw_volume: float, symbol_info) -> float:
    if raw_volume <= 0:
        raise ValueError('copy volume must be greater than 0')
    volume_min = float(getattr(symbol_info, 'volume_min', 0.01) or 0.01)
    volume_step = float(getattr(symbol_info, 'volume_step', 0.01) or 0.01)
    volume = max(raw_volume, volume_min)
    steps = math.floor((volume - volume_min) / volume_step + 0.000001)
    normalized = volume_min + steps * volume_step
    return round(max(normalized, volume_min), 8)


def copy_position_to_follower(
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
) -> tuple[bool, str, str, str]:
    if follower.connection_type == 'simulated':
        return True, f'Simulated copy {relationship.source_symbol} to {relationship.follower_symbol}', source_position.get('position_id', ''), ''
    if follower.connection_type != 'mt5_terminal':
        return False, f'Unsupported follower connection type: {follower.connection_type}', '', ''

    with mt5_connection_lock():
        success, detail = init_mt5_account(follower.terminal_path, follower.login, follower.password, follower.server)
        if not success:
            return False, detail or f'Failed to connect follower account {follower.name}', '', ''

        try:
            symbol = relationship.follower_symbol
            if not mt5.symbol_select(symbol, True):
                return False, f'Failed to select follower symbol {symbol}. Error: {mt5.last_error()}', '', ''

            symbol_info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            if symbol_info is None or tick is None:
                return False, f'Missing tick or symbol info for follower symbol {symbol}. Error: {mt5.last_error()}', '', ''

            is_buy = _position_is_buy(source_position)
            order_type = getattr(mt5, 'ORDER_TYPE_BUY', 0) if is_buy else getattr(mt5, 'ORDER_TYPE_SELL', 1)
            price = float(getattr(tick, 'ask', 0) if is_buy else getattr(tick, 'bid', 0))
            if price <= 0:
                return False, f'Missing executable price for follower symbol {symbol}', '', ''

            source_volume = float(source_position.get('volume') or 0)
            try:
                volume = _normalize_volume(source_volume * relationship.lot_multiplier, symbol_info)
            except ValueError as error:
                return False, str(error), '', ''
            request = {
                'action': getattr(mt5, 'TRADE_ACTION_DEAL', 1),
                'symbol': symbol,
                'volume': volume,
                'type': order_type,
                'price': price,
                'deviation': 20,
                'magic': 260526,
                'comment': f'local-copy:{relationship.id[:16]}',
                'type_time': getattr(mt5, 'ORDER_TIME_GTC', 0),
                'type_filling': getattr(mt5, 'ORDER_FILLING_IOC', 1),
            }
            result = mt5.order_send(request)
            if result is None:
                return False, f'MT5 order_send returned no result. Error: {mt5.last_error()}', '', ''

            result_code = getattr(result, 'retcode', None)
            done_codes = {
                getattr(mt5, 'TRADE_RETCODE_DONE', 10009),
                getattr(mt5, 'TRADE_RETCODE_PLACED', 10008),
            }
            if result_code not in done_codes:
                comment = getattr(result, 'comment', '')
                return False, f'MT5 order_send failed. Retcode: {result_code}. {comment}', '', ''

            order_id = getattr(result, 'order', '') or getattr(result, 'deal', '')
            follower_position_id = _find_follower_position_id(symbol, order_id)
            return True, f'Copied {relationship.source_symbol} to {symbol}, volume {volume}, order {order_id}', follower_position_id, str(order_id or '')
        finally:
            shutdown_mt5()


def _find_follower_position_id(symbol: str, order_id) -> str:
    try:
        positions = mt5.positions_get(symbol=symbol) or mt5.positions_get() or []
    except TypeError:
        positions = mt5.positions_get() or []
    except Exception:
        return ''

    order_text = str(order_id or '')
    for position in positions:
        payload = position._asdict() if hasattr(position, '_asdict') else dict(position)
        if str(payload.get('ticket') or '') == order_text:
            return str(payload.get('ticket') or '')
        if str(payload.get('identifier') or '') == order_text:
            return str(payload.get('ticket') or payload.get('identifier') or '')
        if str(payload.get('symbol') or '').casefold() == symbol.casefold():
            return str(payload.get('ticket') or payload.get('identifier') or '')
    return ''


def close_copied_position_on_follower(
    follower: FollowerAccount,
    relationship: CopyRelationship,
    copied_event: SyncEvent,
) -> tuple[bool, str]:
    if follower.connection_type == 'simulated':
        return True, f'Simulated close {copied_event.follower_position_id or copied_event.position_id}'
    if follower.connection_type != 'mt5_terminal':
        return False, f'Unsupported follower connection type: {follower.connection_type}'

    with mt5_connection_lock():
        success, detail = init_mt5_account(follower.terminal_path, follower.login, follower.password, follower.server)
        if not success:
            return False, detail or f'Failed to connect follower account {follower.name}'

        try:
            target_position = _find_position_to_close(copied_event)
            if target_position is None:
                return True, f'Follower position already closed for source position {copied_event.position_id}'

            symbol = str(target_position.get('symbol') or copied_event.symbol or relationship.follower_symbol)
            if not mt5.symbol_select(symbol, True):
                return False, f'Failed to select follower symbol {symbol}. Error: {mt5.last_error()}'

            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return False, f'Missing tick for follower symbol {symbol}. Error: {mt5.last_error()}'

            is_buy = _position_is_buy(target_position)
            order_type = getattr(mt5, 'ORDER_TYPE_SELL', 1) if is_buy else getattr(mt5, 'ORDER_TYPE_BUY', 0)
            price = float(getattr(tick, 'bid', 0) if is_buy else getattr(tick, 'ask', 0))
            if price <= 0:
                return False, f'Missing close price for follower symbol {symbol}'

            position_ticket = int(target_position.get('ticket') or target_position.get('identifier') or 0)
            volume = float(target_position.get('volume') or 0)
            if position_ticket <= 0 or volume <= 0:
                return False, f'Invalid follower position data for {symbol}'

            request = {
                'action': getattr(mt5, 'TRADE_ACTION_DEAL', 1),
                'symbol': symbol,
                'volume': volume,
                'type': order_type,
                'position': position_ticket,
                'price': price,
                'deviation': 20,
                'magic': 260526,
                'comment': f'local-close:{relationship.id[:15]}',
                'type_time': getattr(mt5, 'ORDER_TIME_GTC', 0),
                'type_filling': getattr(mt5, 'ORDER_FILLING_IOC', 1),
            }
            result = mt5.order_send(request)
            if result is None:
                return False, f'MT5 close order_send returned no result. Error: {mt5.last_error()}'

            result_code = getattr(result, 'retcode', None)
            done_codes = {
                getattr(mt5, 'TRADE_RETCODE_DONE', 10009),
                getattr(mt5, 'TRADE_RETCODE_PLACED', 10008),
            }
            if result_code not in done_codes:
                comment = getattr(result, 'comment', '')
                return False, f'MT5 close order_send failed. Retcode: {result_code}. {comment}'

            order_id = getattr(result, 'order', '') or getattr(result, 'deal', '')
            return True, f'Closed follower position {position_ticket}, order {order_id}'
        finally:
            shutdown_mt5()


def _find_position_to_close(copied_event: SyncEvent) -> dict | None:
    target_ids = {copied_event.follower_position_id, copied_event.follower_order_id} - {''}
    try:
        positions = mt5.positions_get(symbol=copied_event.symbol) or mt5.positions_get() or []
    except TypeError:
        positions = mt5.positions_get() or []

    fallback = None
    for position in positions:
        payload = position._asdict() if hasattr(position, '_asdict') else dict(position)
        ticket = str(payload.get('ticket') or '')
        identifier = str(payload.get('identifier') or '')
        if ticket in target_ids or identifier in target_ids:
            return payload
        if fallback is None and str(payload.get('symbol') or '').casefold() == copied_event.symbol.casefold():
            fallback = payload
    return fallback
