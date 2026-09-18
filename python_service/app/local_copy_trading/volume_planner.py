"""Decide the follower volume for one copied position.

Four sizing modes are supported. All of them end in the same place: a volume
that has been clamped to the follower symbol's contract limits and to the
relationship's own ceiling, so the caller never has to think about broker
granularity.

The module is pure: it takes account figures and symbol metadata as arguments
instead of reading them, which keeps it testable and keeps the MT5 connection
out of the sizing decision.
"""

from __future__ import annotations

import math

from python_service.app.local_copy_trading.models import CopyRelationship


VOLUME_MODES = ('multiplier', 'fixed', 'equity_ratio', 'risk_percent')


def normalize_volume(raw_volume: float, symbol_info) -> float:
    """Snap a volume to the symbol's minimum, maximum and step."""
    if raw_volume <= 0:
        raise ValueError('copy volume must be greater than 0')

    volume_min = float(getattr(symbol_info, 'volume_min', 0.01) or 0.01)
    volume_max = float(getattr(symbol_info, 'volume_max', 0) or 0)
    volume_step = float(getattr(symbol_info, 'volume_step', 0.01) or 0.01)

    volume = max(raw_volume, volume_min)
    if volume_max > 0:
        volume = min(volume, volume_max)

    steps = math.floor((volume - volume_min) / volume_step + 0.000001)
    normalized = volume_min + steps * volume_step
    if volume_max > 0:
        normalized = min(normalized, volume_max)
    return round(max(normalized, volume_min), 8)


def plan_volume(
    relationship: CopyRelationship,
    source_position: dict,
    *,
    symbol_info,
    source_equity: float | None = None,
    follower_equity: float | None = None,
) -> float:
    """Return the follower volume for this relationship and source position.

    Raises:
        ValueError: when the inputs cannot produce a positive volume.
    """
    source_volume = float(source_position.get('volume') or 0)
    mode = relationship.volume_mode

    if mode == 'multiplier':
        raw_volume = source_volume * relationship.lot_multiplier
    elif mode == 'fixed':
        raw_volume = relationship.lot_multiplier
    elif mode == 'equity_ratio':
        if source_equity is None or follower_equity is None:
            raise ValueError('equity_ratio sizing requires both account equities')
        if float(source_equity) <= 0:
            raise ValueError('source equity must be greater than 0')
        raw_volume = source_volume * (float(follower_equity) / float(source_equity)) * relationship.lot_multiplier
    elif mode == 'risk_percent':
        raw_volume = _volume_from_risk(relationship, source_position, source_equity, symbol_info)
    else:
        raise ValueError(f'Unsupported volume mode: {mode}')

    if raw_volume <= 0:
        raise ValueError('copy volume must be greater than 0')

    if relationship.max_lot > 0:
        raw_volume = min(raw_volume, relationship.max_lot)

    return normalize_volume(raw_volume, symbol_info)


def plan_volume_delta(
    expected_volume: float,
    actual_volume: float,
    *,
    symbol_info,
    tolerance: float = 0.0,
) -> float:
    """Return the volume to add or remove on an already-open follower position.

    Positive means scale in, negative means partially close, 0 means the
    position already matches. Differences smaller than one tradeable step are
    ignored so the engine does not send orders the broker would reject as
    zero-volume.
    """
    delta = round(float(expected_volume) - float(actual_volume), 8)
    step = float(getattr(symbol_info, 'volume_step', 0.01) or 0.01)
    if step > 0 and abs(delta) < step:
        return 0.0
    if tolerance > 0 and abs(delta) <= tolerance:
        return 0.0
    return delta


def _volume_from_risk(
    relationship: CopyRelationship,
    source_position: dict,
    source_equity: float | None,
    symbol_info,
) -> float:
    """Size so that the follower risks a fixed fraction of the source equity.

    Uses the source position's stop distance as the risk unit, converted to
    money through the follower symbol's contract size. This assumes the account
    currency and the instrument's quote currency match, which holds for the
    USD-quoted symbols this tool targets; a cross-currency instrument would need
    a conversion rate here.
    """
    if source_equity is None:
        raise ValueError('risk_percent sizing requires the source equity')

    entry = float(source_position.get('price_open') or 0)
    stop = float(source_position.get('sl') or 0)
    if entry <= 0 or stop <= 0:
        raise ValueError('risk_percent sizing requires a source position with a stop loss')

    stop_distance = abs(entry - stop)
    if stop_distance <= 0:
        raise ValueError('risk_percent sizing requires a non-zero stop distance')

    contract_size = float(getattr(symbol_info, 'trade_contract_size', 0) or 0)
    if contract_size <= 0:
        raise ValueError('risk_percent sizing requires a known contract size')

    risk_amount = float(source_equity) * (relationship.risk_percent / 100.0)
    return risk_amount / (stop_distance * contract_size)
