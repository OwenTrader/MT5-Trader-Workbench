"""At-rest credential encryption via Windows DPAPI (crypt32), no extra deps.

Scope: values persisted into the storage JSON files (MT5 account passwords,
TopStep API keys, AI keys, bot secrets). The API layer still serves
plaintext to the local renderer; this protects the files on disk.

Format: ``dpapi:<base64>``. Values without the prefix are treated as
plaintext and keep working, so existing installs upgrade lazily the next
time they save. On non-Windows or DPAPI failure the helpers are transparent
pass-throughs rather than hard failures.
"""

from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes

_PREFIX = 'dpapi:'
_ENABLED = os.name == 'nt'


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ('cbData', wintypes.DWORD),
        ('pbData', ctypes.POINTER(ctypes.c_byte)),
    ]


def _blob_from_bytes(data: bytes) -> _DATA_BLOB:
    buffer = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))


def _bytes_from_blob(blob: _DATA_BLOB) -> bytes:
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob.pbData)


def _protect(data: bytes) -> bytes:
    in_blob = _blob_from_bytes(data)
    out_blob = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob), 'MT5Workbench', None, None, None, 0, ctypes.byref(out_blob)
    )
    if not ok:
        raise OSError('CryptProtectData failed')
    return _bytes_from_blob(out_blob)


def _unprotect(data: bytes) -> bytes:
    in_blob = _blob_from_bytes(data)
    out_blob = _DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    )
    if not ok:
        raise OSError('CryptUnprotectData failed')
    return _bytes_from_blob(out_blob)


def encrypt(value: str | None) -> str | None:
    if not value or not _ENABLED:
        return value
    if value.startswith(_PREFIX):
        return value  # already sealed
    try:
        sealed = _protect(value.encode('utf-8'))
    except OSError:
        return value
    return _PREFIX + base64.b64encode(sealed).decode('ascii')


def decrypt(value: str | None) -> str | None:
    if not value or not value.startswith(_PREFIX):
        return value
    if not _ENABLED:
        return value
    try:
        return _unprotect(base64.b64decode(value[len(_PREFIX):])).decode('utf-8')
    except (OSError, ValueError):
        # Sealed on another machine/user: unusable, but crashing storage
        # loads would be worse. Treat as empty credential.
        return ''


def is_sealed(value: str | None) -> bool:
    return bool(value) and bool(value.startswith(_PREFIX))
