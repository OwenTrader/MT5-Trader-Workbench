"""SQLite persistence for the local copy trading order map.

The order map is the authoritative record of "this follower position was opened
for this source position". It has to survive process restarts, because the
whole point is to recognise an order that was already sent before a crash.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path('storage/local_copy_trading.db')

OPEN_STATUSES = ('pending', 'confirmed')

_SCHEMA = """
CREATE TABLE IF NOT EXISTS copy_order_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_key TEXT NOT NULL UNIQUE,
    relationship_id TEXT NOT NULL,
    source_account_id TEXT NOT NULL,
    follower_account_id TEXT NOT NULL,
    source_position_id TEXT NOT NULL,
    status TEXT NOT NULL,
    follower_position_ticket TEXT NOT NULL DEFAULT '',
    follower_order_id TEXT NOT NULL DEFAULT '',
    source_volume REAL NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_copy_order_map_lookup
    ON copy_order_map (relationship_id, source_position_id);
CREATE INDEX IF NOT EXISTS idx_copy_order_map_status
    ON copy_order_map (status);
CREATE INDEX IF NOT EXISTS idx_copy_order_map_follower
    ON copy_order_map (follower_account_id);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> None:
    connection = connect(db_path)
    try:
        connection.executescript(_SCHEMA)
        _ensure_column(connection, 'copy_order_map', 'source_volume', 'REAL NOT NULL DEFAULT 0')
        connection.commit()
    finally:
        connection.close()


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add a column to an existing table when it predates the current schema.

    ``CREATE TABLE IF NOT EXISTS`` silently leaves an old table alone, so a
    database written by an earlier version would be missing newly added columns.
    This keeps an in-place upgrade working without a separate migration step.
    """
    existing = {row[1] for row in connection.execute(f'PRAGMA table_info({table})').fetchall()}
    if column not in existing:
        connection.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def insert_pending(
    *,
    client_key: str,
    relationship_id: str,
    source_account_id: str,
    follower_account_id: str,
    source_position_id: str,
    created_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> bool:
    """Record an intended order.

    Returns True when a new row was created and False when the client key was
    already present, which is how a retry after a crash is recognised.
    """
    connection = connect(db_path)
    try:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO copy_order_map (
                client_key, relationship_id, source_account_id, follower_account_id,
                source_position_id, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                client_key,
                relationship_id,
                source_account_id,
                follower_account_id,
                source_position_id,
                created_at,
                created_at,
            ),
        )
        connection.commit()
        return cursor.rowcount == 1
    finally:
        connection.close()


def _set_status(
    client_key: str,
    status: str,
    *,
    message: str,
    updated_at: str,
    follower_position_ticket: str = '',
    follower_order_id: str = '',
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    connection = connect(db_path)
    try:
        connection.execute(
            """
            UPDATE copy_order_map
               SET status = ?,
                   message = ?,
                   updated_at = ?,
                   follower_position_ticket = CASE WHEN ? <> '' THEN ? ELSE follower_position_ticket END,
                   follower_order_id = CASE WHEN ? <> '' THEN ? ELSE follower_order_id END
             WHERE client_key = ?
            """,
            (
                status,
                message,
                updated_at,
                follower_position_ticket,
                follower_position_ticket,
                follower_order_id,
                follower_order_id,
                client_key,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def confirm_order(
    client_key: str,
    *,
    follower_position_ticket: str = '',
    follower_order_id: str = '',
    message: str = '',
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    _set_status(
        client_key,
        'confirmed',
        message=message,
        updated_at=updated_at,
        follower_position_ticket=follower_position_ticket,
        follower_order_id=follower_order_id,
        db_path=db_path,
    )


def record_source_volume(
    client_key: str,
    *,
    source_volume: float,
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    """Remember the source size this copy last matched.

    The next tick compares the live source volume against this value to decide
    whether the follower needs a partial close or a scale in. Recording it after
    every action is what makes the comparison settle instead of firing forever.
    """
    connection = connect(db_path)
    try:
        connection.execute(
            """
            UPDATE copy_order_map
               SET source_volume = ?, updated_at = ?
             WHERE client_key = ?
            """,
            (float(source_volume), updated_at, client_key),
        )
        connection.commit()
    finally:
        connection.close()


def get_recorded_volume(
    relationship_id: str,
    source_position_id: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> float | None:
    """Return the source volume last matched for this pair, or None if unknown."""
    connection = connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT source_volume FROM copy_order_map
             WHERE relationship_id = ? AND source_position_id = ?
             ORDER BY id DESC
             LIMIT 1
            """,
            (relationship_id, source_position_id),
        ).fetchone()
        if row is None:
            return None
        return float(row['source_volume'] or 0)
    finally:
        connection.close()


def mark_failed(
    client_key: str,
    *,
    message: str,
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    _set_status(client_key, 'failed', message=message, updated_at=updated_at, db_path=db_path)


def mark_closed(
    client_key: str,
    *,
    message: str,
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    _set_status(client_key, 'closed', message=message, updated_at=updated_at, db_path=db_path)


def mark_drifted(
    client_key: str,
    *,
    message: str,
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    _set_status(client_key, 'drifted', message=message, updated_at=updated_at, db_path=db_path)


def mark_skipped(
    client_key: str,
    *,
    message: str,
    updated_at: str,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    """Settle a record whose order a pre-trade guard refused to send."""
    _set_status(client_key, 'skipped', message=message, updated_at=updated_at, db_path=db_path)


def find_by_client_key(client_key: str, *, db_path: Path | str = DEFAULT_DB_PATH) -> dict | None:
    connection = connect(db_path)
    try:
        row = connection.execute(
            'SELECT * FROM copy_order_map WHERE client_key = ?',
            (client_key,),
        ).fetchone()
        return _row_to_dict(row)
    finally:
        connection.close()


def list_open_records(*, db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    """Return every record that claims a follower position should exist."""
    connection = connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT * FROM copy_order_map
             WHERE status IN (?, ?)
             ORDER BY id
            """,
            OPEN_STATUSES,
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        connection.close()


def delete_by_relationship(relationship_id: str, *, db_path: Path | str = DEFAULT_DB_PATH) -> None:
    connection = connect(db_path)
    try:
        connection.execute(
            'DELETE FROM copy_order_map WHERE relationship_id = ?',
            (relationship_id,),
        )
        connection.commit()
    finally:
        connection.close()
