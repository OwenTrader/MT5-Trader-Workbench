"""Execute follower-side MT5 orders against an already-open session.

The caller owns the connection (see ``services.mt5_session``). This module only
builds and validates order requests, so it can be tested without a terminal.

Follower positions are identified by the ownership token written into the order
comment (see ``position_ownership``). There is deliberately no symbol-based
fallback: matching the wrong position on a live account is worse than reporting
that nothing was found.

Order placement is split in two: ``plan_copy_order`` decides size and protective
levels without touching the broker, and ``send_copy_order`` transmits the
request. The split exists so that pre-trade guards can inspect a fully planned
order (they need the volume) before anything reaches the broker.
"""

from dataclasses import dataclass

from python_service.app.local_copy_trading import position_ownership, price_mapping, volume_planner
from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount, SyncEvent


@dataclass(frozen=True)
class CopyPlan:
    """A follower order that has been sized and priced but not yet sent.

    ``short_circuit`` carries a finished result for the cases that never produce
    a request at all (simulated followers, unsupported connection types). When it
    is set the caller must return it unchanged.
    """

    ok: bool
    message: str = ''
    request: dict | None = None
    volume: float = 0.0
    short_circuit: tuple | None = None


def as_dict(value) -> dict:
    """Normalise an MT5 namedtuple-like result into a plain dict."""
    if hasattr(value, '_asdict'):
        return value._asdict()
    if isinstance(value, dict):
        return value
    return dict(value)


_as_dict = as_dict


def list_positions(client, symbol: str | None = None) -> list[dict]:
    """Read open positions as plain dicts, tolerating brokers that ignore filters."""
    try:
        positions = client.positions_get(symbol=symbol) if symbol else client.positions_get()
    except TypeError:
        positions = client.positions_get()
    except Exception:
        return []
    return [_as_dict(position) for position in (positions or [])]


def _position_is_buy(position: dict, client) -> bool:
    value = position.get('type')
    if isinstance(value, str):
        return value.strip().casefold() in {'buy', 'long', '0'}
    return int(value or 0) == getattr(client, 'POSITION_TYPE_BUY', 0)


def _done_codes(client) -> set:
    return {
        getattr(client, 'TRADE_RETCODE_DONE', 10009),
        getattr(client, 'TRADE_RETCODE_PLACED', 10008),
    }


def find_owned_position(
    client,
    symbol: str,
    *,
    relationship_id: str,
    position_id: str,
) -> dict | None:
    """Locate the follower position owned by this relationship/source pair.

    Returns None when the position is absent. Callers must treat None as
    "nothing to act on" rather than falling back to another position.
    """
    try:
        positions = client.positions_get(symbol=symbol)
    except TypeError:
        positions = client.positions_get()
    except Exception:
        return None

    return position_ownership.select_owned_position(
        [_as_dict(position) for position in (positions or [])],
        relationship_id=relationship_id,
        position_id=position_id,
    )


def plan_copy_order(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
) -> CopyPlan:
    """Size and price a follower order without sending it.

    Returns a plan whose ``short_circuit`` is set when no order will ever be
    built, and whose ``ok`` is False when the inputs cannot produce a request.
    """
    if follower.connection_type == 'simulated':
        message = f'Simulated copy {relationship.source_symbol} to {relationship.follower_symbol}'
        return CopyPlan(
            ok=True,
            message=message,
            short_circuit=(True, message, source_position.get('position_id', ''), ''),
        )
    if follower.connection_type != 'mt5_terminal':
        return CopyPlan(ok=False, message=f'Unsupported follower connection type: {follower.connection_type}')

    position_id = str(source_position.get('position_id') or source_position.get('ticket') or '')
    if not position_id:
        return CopyPlan(ok=False, message='Source position has no identifier')

    symbol = relationship.follower_symbol
    if not client.symbol_select(symbol, True):
        return CopyPlan(ok=False, message=f'Failed to select follower symbol {symbol}. Error: {client.last_error()}')

    symbol_info = client.symbol_info(symbol)
    tick = client.symbol_info_tick(symbol)
    if symbol_info is None or tick is None:
        return CopyPlan(
            ok=False,
            message=f'Missing tick or symbol info for follower symbol {symbol}. Error: {client.last_error()}',
        )

    is_buy = _position_is_buy(source_position, client)
    order_type = getattr(client, 'ORDER_TYPE_BUY', 0) if is_buy else getattr(client, 'ORDER_TYPE_SELL', 1)
    price = float(getattr(tick, 'ask', 0) if is_buy else getattr(tick, 'bid', 0))
    if price <= 0:
        return CopyPlan(ok=False, message=f'Missing executable price for follower symbol {symbol}')

    follower_equity = None
    if relationship.volume_mode == 'equity_ratio':
        account_info = client.account_info()
        if account_info is not None:
            follower_equity = float(getattr(account_info, 'equity', 0) or 0)

    try:
        volume = volume_planner.plan_volume(
            relationship,
            source_position,
            symbol_info=symbol_info,
            source_equity=source_position.get('source_equity'),
            follower_equity=follower_equity,
        )
    except ValueError as error:
        return CopyPlan(ok=False, message=str(error))

    stop_loss = 0.0
    take_profit = 0.0
    if relationship.sync_sl_tp:
        raw_stop, raw_target = price_mapping.translate_protective_levels(
            source_position,
            follower_entry=price,
        )
        stop_loss = price_mapping.normalize_price(raw_stop, symbol_info)
        take_profit = price_mapping.normalize_price(raw_target, symbol_info)

    request = {
        'action': getattr(client, 'TRADE_ACTION_DEAL', 1),
        'symbol': symbol,
        'volume': volume,
        'type': order_type,
        'price': price,
        'sl': stop_loss,
        'tp': take_profit,
        'deviation': 20,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment(relationship.id, position_id),
        'type_time': getattr(client, 'ORDER_TIME_GTC', 0),
        'type_filling': getattr(client, 'ORDER_FILLING_IOC', 1),
    }
    return CopyPlan(ok=True, request=request, volume=volume)


def send_copy_order(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    plan: CopyPlan,
    source_position: dict,
) -> tuple[bool, str, str, str]:
    """Transmit a plan produced by :func:`plan_copy_order`."""
    if plan.short_circuit is not None:
        return plan.short_circuit
    if not plan.ok or plan.request is None:
        return False, plan.message, '', ''

    symbol = plan.request['symbol']
    position_id = str(source_position.get('position_id') or source_position.get('ticket') or '')
    result = client.order_send(plan.request)
    if result is None:
        return False, f'MT5 order_send returned no result. Error: {client.last_error()}', '', ''

    result_code = getattr(result, 'retcode', None)
    if result_code not in _done_codes(client):
        comment = getattr(result, 'comment', '')
        return False, f'MT5 order_send failed. Retcode: {result_code}. {comment}', '', ''

    order_id = getattr(result, 'order', '') or getattr(result, 'deal', '')
    owned = find_owned_position(
        client,
        symbol,
        relationship_id=relationship.id,
        position_id=position_id,
    )
    follower_position_id = str(owned.get('ticket') or '') if owned else ''
    return (
        True,
        f'Copied {relationship.source_symbol} to {symbol}, volume {plan.volume}, order {order_id}',
        follower_position_id,
        str(order_id or ''),
    )


def copy_position_to_follower(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
) -> tuple[bool, str, str, str]:
    """Open a follower position mirroring ``source_position``.

    Returns ``(success, message, follower_position_id, follower_order_id)``.
    """
    plan = plan_copy_order(client, follower, relationship, source_position)
    if plan.short_circuit is not None:
        return plan.short_circuit
    if not plan.ok:
        return False, plan.message, '', ''
    return send_copy_order(client, follower, relationship, plan, source_position)


def adjust_copied_position_volume(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
    *,
    expected_volume: float,
) -> tuple[bool, str]:
    """Bring an already-open follower position to ``expected_volume``.

    A source position can shrink (the source trader takes partial profit) or grow
    (the source trader scales in) while keeping the same ticket. Mirroring that
    means sending either a partial close or an additional deal, never a new
    independent position.

    Returns ``(success, message)``. A position that already matches is reported
    as success so the caller can settle the record without further action.
    """
    if follower.connection_type == 'simulated':
        return True, f'Simulated volume sync to {expected_volume}'
    if follower.connection_type != 'mt5_terminal':
        return False, f'Unsupported follower connection type: {follower.connection_type}'

    position_id = str(source_position.get('position_id') or source_position.get('ticket') or '')
    symbol = relationship.follower_symbol
    owned = find_owned_position(
        client,
        symbol,
        relationship_id=relationship.id,
        position_id=position_id,
    )
    if owned is None:
        return False, f'No owned follower position for source position {position_id}'

    if not client.symbol_select(symbol, True):
        return False, f'Failed to select follower symbol {symbol}. Error: {client.last_error()}'

    symbol_info = client.symbol_info(symbol)
    tick = client.symbol_info_tick(symbol)
    if symbol_info is None or tick is None:
        return False, f'Missing tick or symbol info for follower symbol {symbol}. Error: {client.last_error()}'

    actual_volume = float(owned.get('volume') or 0)
    delta = volume_planner.plan_volume_delta(expected_volume, actual_volume, symbol_info=symbol_info)
    if delta == 0:
        return True, f'Follower position already matches {actual_volume} lots'

    position_ticket = int(owned.get('ticket') or 0)
    is_buy = _position_is_buy(owned, client)
    scaling_in = delta > 0
    order_type = (
        (getattr(client, 'ORDER_TYPE_BUY', 0) if is_buy else getattr(client, 'ORDER_TYPE_SELL', 1))
        if scaling_in
        else (getattr(client, 'ORDER_TYPE_SELL', 1) if is_buy else getattr(client, 'ORDER_TYPE_BUY', 0))
    )
    price = float(getattr(tick, 'ask', 0) if is_buy else getattr(tick, 'bid', 0))
    if price <= 0:
        return False, f'Missing adjustment price for follower symbol {symbol}'

    request = {
        'action': getattr(client, 'TRADE_ACTION_DEAL', 1),
        'symbol': symbol,
        'volume': volume_planner.normalize_volume(abs(delta), symbol_info),
        'type': order_type,
        'price': price,
        'deviation': 20,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment(relationship.id, position_id),
        'type_time': getattr(client, 'ORDER_TIME_GTC', 0),
        'type_filling': getattr(client, 'ORDER_FILLING_IOC', 1),
    }
    if not scaling_in:
        request['position'] = position_ticket

    result = client.order_send(request)
    if result is None:
        return False, f'MT5 volume adjustment returned no result. Error: {client.last_error()}'

    result_code = getattr(result, 'retcode', None)
    if result_code not in _done_codes(client):
        comment = getattr(result, 'comment', '')
        return False, f'MT5 volume adjustment failed. Retcode: {result_code}. {comment}'

    action = 'Scaled in' if scaling_in else 'Partially closed'
    return True, f'{action} follower position {position_ticket} by {abs(delta):.2f} lots to {expected_volume}'


def close_copied_position_on_follower(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    copied_event: SyncEvent,
) -> tuple[bool, str]:
    """Close the follower position owned by ``copied_event``."""
    if follower.connection_type == 'simulated':
        return True, f'Simulated close {copied_event.follower_position_id or copied_event.position_id}'
    if follower.connection_type != 'mt5_terminal':
        return False, f'Unsupported follower connection type: {follower.connection_type}'

    target_position = find_owned_position(
        client,
        copied_event.symbol,
        relationship_id=relationship.id,
        position_id=copied_event.position_id,
    )
    if target_position is None:
        return True, f'No owned follower position for source position {copied_event.position_id}; nothing to close'

    symbol = str(target_position.get('symbol') or copied_event.symbol or relationship.follower_symbol)
    if not client.symbol_select(symbol, True):
        return False, f'Failed to select follower symbol {symbol}. Error: {client.last_error()}'

    tick = client.symbol_info_tick(symbol)
    if tick is None:
        return False, f'Missing tick for follower symbol {symbol}. Error: {client.last_error()}'

    is_buy = _position_is_buy(target_position, client)
    order_type = getattr(client, 'ORDER_TYPE_SELL', 1) if is_buy else getattr(client, 'ORDER_TYPE_BUY', 0)
    price = float(getattr(tick, 'bid', 0) if is_buy else getattr(tick, 'ask', 0))
    if price <= 0:
        return False, f'Missing close price for follower symbol {symbol}'

    position_ticket = int(target_position.get('ticket') or 0)
    volume = float(target_position.get('volume') or 0)
    if position_ticket <= 0 or volume <= 0:
        return False, f'Invalid follower position data for {symbol}'

    request = {
        'action': getattr(client, 'TRADE_ACTION_DEAL', 1),
        'symbol': symbol,
        'volume': volume,
        'type': order_type,
        'position': position_ticket,
        'price': price,
        'deviation': 20,
        'magic': position_ownership.COPY_TRADING_MAGIC,
        'comment': position_ownership.build_comment(relationship.id, copied_event.position_id),
        'type_time': getattr(client, 'ORDER_TIME_GTC', 0),
        'type_filling': getattr(client, 'ORDER_FILLING_IOC', 1),
    }
    result = client.order_send(request)
    if result is None:
        return False, f'MT5 close order_send returned no result. Error: {client.last_error()}'

    result_code = getattr(result, 'retcode', None)
    if result_code not in _done_codes(client):
        comment = getattr(result, 'comment', '')
        return False, f'MT5 close order_send failed. Retcode: {result_code}. {comment}'

    order_id = getattr(result, 'order', '') or getattr(result, 'deal', '')
    return True, f'Closed follower position {position_ticket}, order {order_id}'
