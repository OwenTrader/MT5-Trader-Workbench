"""Shared origin allowlist for HTTP and WebSocket entry points.

The local trading API must not be reachable from arbitrary web pages (a
malicious site could read accounts/positions or place orders). The Electron
renderer is either a file:// origin (packaged, Origin: "null") or
http://localhost/127.0.0.1 (dev). Anything else is rejected.
"""

from __future__ import annotations

import os

_DEV_CORS_ORIGIN = os.environ.get('ALLOWED_CORS_ORIGIN')


def is_allowed_origin(origin: str | None) -> bool:
    if origin is None or origin == 'null':
        return True
    if _DEV_CORS_ORIGIN and origin == _DEV_CORS_ORIGIN:
        return True
    return origin.startswith(('http://localhost:', 'http://127.0.0.1:'))
