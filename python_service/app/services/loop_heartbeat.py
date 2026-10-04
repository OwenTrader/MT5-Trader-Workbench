"""Heartbeat tracker for the long-running background loops.

/health reports each loop's last tick so a silently dead loop (crashed task,
hung MT5 call) is visible from the outside instead of "ok" forever.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

_last_tick: dict[str, float] = {}


def record(loop_name: str) -> None:
    _last_tick[loop_name] = time.monotonic()


def snapshot() -> dict[str, dict[str, float | None]]:
    now = time.monotonic()
    return {
        name: {
            'age_seconds': None if stamp is None else round(now - stamp, 1),
        }
        for name, stamp in _last_tick.items()
    }


def reset() -> None:
    """Test helper: forget all recorded heartbeats."""
    _last_tick.clear()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
