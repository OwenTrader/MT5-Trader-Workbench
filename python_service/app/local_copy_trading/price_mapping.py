"""Translate source protective levels onto the follower's price scale.

Stop loss and take profit cannot be copied as raw prices. The follower opens at
its own price on its own broker, so the only meaningful thing to carry across is
the *distance* from entry, together with which side of entry the level sits on.

Deriving the side from the source level itself (rather than from the trade
direction) is what keeps a take profit above entry for a long position and below
entry for a short one.
"""

from __future__ import annotations


def translate_protective_levels(
    source_position: dict,
    *,
    follower_entry: float,
    ratio: float = 1.0,
) -> tuple[float, float]:
    """Return ``(stop_loss, take_profit)`` on the follower's price scale.

    A source level of 0 (not set) stays 0, so the follower simply has no stop on
    that side. ``ratio`` scales the distance for instruments quoted on a
    different scale between the two brokers; it is 1.0 for identical symbols.

    Returns ``(0.0, 0.0)`` when the source entry price is unknown, because a
    distance cannot be derived from nothing.
    """
    source_entry = float(source_position.get('price_open') or 0)
    if source_entry <= 0 or follower_entry <= 0:
        return 0.0, 0.0

    def translate(level_key: str) -> float:
        level = float(source_position.get(level_key) or 0)
        if level <= 0:
            return 0.0
        distance = abs(source_entry - level) * ratio
        return follower_entry - distance if level < source_entry else follower_entry + distance

    return translate('sl'), translate('tp')


def normalize_price(price: float, symbol_info) -> float:
    """Round a price to the symbol's digits so MT5 accepts the request."""
    if price <= 0:
        return 0.0
    digits = int(getattr(symbol_info, 'digits', 0) or 0)
    return round(price, digits)
