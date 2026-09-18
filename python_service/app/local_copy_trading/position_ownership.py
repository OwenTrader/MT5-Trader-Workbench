"""Ownership tokens for follower positions.

An MT5 position carries the ``magic`` number and the ``comment`` of the order
that opened it. Those two fields are the only reliable way to tell a position
this tool opened for a specific source position apart from a manual position or
another EA's position in the same symbol.

The comment is capped at 31 characters by MT5, so identifiers are hashed to
eight hex characters each: ``lc:<8>:<8>`` is 20 characters.
"""

from __future__ import annotations

import hashlib

COPY_TRADING_MAGIC = 260526
COMMENT_PREFIX = 'lc'
MAX_COMMENT_LENGTH = 31


def short_token(value: str) -> str:
    """Return a stable eight-character token for an identifier."""
    return hashlib.sha1(str(value or '').encode('utf-8')).hexdigest()[:8]


def build_comment(relationship_id: str, position_id: str) -> str:
    """Build the comment that marks a follower order as owned by a relationship."""
    return f'{COMMENT_PREFIX}:{short_token(relationship_id)}:{short_token(position_id)}'


def is_copy_trading_position(payload: dict) -> bool:
    """True when the position was opened by the copy trading module."""
    return int(payload.get('magic') or 0) == COPY_TRADING_MAGIC


def is_owned_position(payload: dict, *, relationship_id: str, position_id: str) -> bool:
    """True when this exact position belongs to this relationship/source pair."""
    if not is_copy_trading_position(payload):
        return False
    return str(payload.get('comment') or '').strip() == build_comment(relationship_id, position_id)


def select_owned_position(positions, *, relationship_id: str, position_id: str) -> dict | None:
    """Return the follower position owned by the given pair, or None.

    Returning None is a meaningful answer: it means the position is gone or was
    never opened. Callers must not fall back to matching by symbol.
    """
    for payload in positions:
        if is_owned_position(payload, relationship_id=relationship_id, position_id=position_id):
            return payload
    return None
