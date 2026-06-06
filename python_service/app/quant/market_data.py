import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from python_service.app.quant.models import Timeframe
from python_service.app.quant.paths import get_market_data_path
from python_service.app.services.mt5_service import fetch_account_bars, fetch_account_bars_range


TIMEFRAME_SECONDS: dict[Timeframe, int] = {
    'M1': 60,
    'M5': 300,
    'M15': 900,
    'M30': 1800,
    'H1': 3600,
    'H4': 14400,
    'D1': 86400,
}


DEFAULT_MARKET_DATA_PATH = get_market_data_path()


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        '''
        create table if not exists bars (
            account_id text not null,
            symbol text not null,
            timeframe text not null,
            time text not null,
            open real not null,
            high real not null,
            low real not null,
            close real not null,
            tick_volume integer not null,
            primary key (account_id, symbol, timeframe, time)
        )
        '''
    )
    return conn


def upsert_bars(
    db_path: Path | str,
    account_id: str,
    symbol: str,
    timeframe: Timeframe,
    bars: list[dict],
) -> int:
    with connect(db_path) as conn:
        conn.executemany(
            '''
            insert into bars (account_id, symbol, timeframe, time, open, high, low, close, tick_volume)
            values (:account_id, :symbol, :timeframe, :time, :open, :high, :low, :close, :tick_volume)
            on conflict(account_id, symbol, timeframe, time) do update set
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                tick_volume=excluded.tick_volume
            ''',
            [{**bar, 'account_id': account_id, 'symbol': symbol, 'timeframe': timeframe} for bar in bars],
        )
        return len(bars)


def load_recent_bars(
    db_path: Path | str,
    account_id: str,
    symbol: str,
    timeframe: Timeframe,
    limit: int,
) -> list[dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            '''
            select time, open, high, low, close, tick_volume
            from bars
            where account_id = ? and symbol = ? and timeframe = ?
            order by time desc
            limit ?
            ''',
            (account_id, symbol, timeframe, limit),
        ).fetchall()

    return [
        {
            'time': row[0],
            'open': row[1],
            'high': row[2],
            'low': row[3],
            'close': row[4],
            'tick_volume': row[5],
        }
        for row in reversed(rows)
    ]


def load_bars_for_range(
    db_path: Path | str,
    account_id: str,
    symbol: str,
    timeframe: Timeframe,
    start_at: str,
    end_at: str,
) -> list[dict]:
    normalized_start_at, normalized_end_at = _normalize_range_bounds(start_at, end_at, timeframe)

    if not _range_is_cached(db_path, account_id, symbol, timeframe, normalized_start_at, normalized_end_at):
        account = _get_runtime_account(account_id)
        fetched = fetch_account_bars_range(
            path=account['terminal_path'],
            login=account['login'],
            password=account['password'],
            server=account['server'],
            symbol=symbol,
            timeframe=timeframe,
            start_at=normalized_start_at,
            end_at=normalized_end_at,
        )
        if fetched:
            upsert_bars(db_path, account_id, symbol, timeframe, fetched)

    with connect(db_path) as conn:
        rows = conn.execute(
            '''
            select time, open, high, low, close, tick_volume
            from bars
            where account_id = ? and symbol = ? and timeframe = ? and time >= ? and time <= ?
            order by time asc
            ''',
            (account_id, symbol, timeframe, normalized_start_at, normalized_end_at),
        ).fetchall()

    return [
        {
            'time': row[0],
            'open': row[1],
            'high': row[2],
            'low': row[3],
            'close': row[4],
            'tick_volume': row[5],
        }
        for row in rows
    ]


def backfill_from_mt5(
    db_path: Path | str,
    account: dict,
    account_id: str,
    symbol: str,
    timeframe: Timeframe,
    bars: int,
) -> int:
    fetched = fetch_account_bars(
        path=account['terminal_path'],
        login=account['login'],
        password=account['password'],
        server=account['server'],
        symbol=symbol,
        timeframe=timeframe,
        count=bars,
    )
    return upsert_bars(db_path, account_id, symbol, timeframe, fetched)


def latest_cached_bar_time(
    db_path: Path | str,
    account_id: str,
    symbol: str,
    timeframe: Timeframe,
) -> str | None:
    rows = load_recent_bars(db_path, account_id, symbol, timeframe, limit=1)
    return rows[0]['time'] if rows else None


def bar_is_stale(latest_time: str, timeframe: Timeframe) -> bool:
    latest = datetime.fromisoformat(latest_time)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - latest).total_seconds()
    return age_seconds >= TIMEFRAME_SECONDS[timeframe]


def stale_backfill_bars(latest_time: str, timeframe: Timeframe) -> int:
    latest = datetime.fromisoformat(latest_time)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)

    age_seconds = max(0.0, (datetime.now(timezone.utc) - latest).total_seconds())
    timeframe_seconds = TIMEFRAME_SECONDS[timeframe]
    missing_bars = int(age_seconds // timeframe_seconds) + 1
    return max(2, missing_bars)


def ensure_recent_bars(
    db_path: Path | str,
    account: dict,
    account_id: str,
    symbol: str,
    timeframe: Timeframe,
    min_bars: int,
) -> list[dict]:
    rows = load_recent_bars(db_path, account_id, symbol, timeframe, limit=min_bars)
    latest_time = rows[-1]['time'] if rows else None

    if len(rows) >= min_bars and latest_time and not bar_is_stale(latest_time, timeframe):
        return rows

    bars_to_fetch = min_bars if len(rows) < min_bars or not latest_time else stale_backfill_bars(latest_time, timeframe)
    backfill_from_mt5(
        db_path=db_path,
        account=account,
        account_id=account_id,
        symbol=symbol,
        timeframe=timeframe,
        bars=bars_to_fetch,
    )
    return load_recent_bars(db_path, account_id, symbol, timeframe, limit=min_bars)


def _range_is_cached(
    db_path: Path | str,
    account_id: str,
    symbol: str,
    timeframe: Timeframe,
    start_at: str,
    end_at: str,
) -> bool:
    with connect(db_path) as conn:
        coverage = conn.execute(
            '''
            select min(time), max(time), count(*)
            from bars
            where account_id = ? and symbol = ? and timeframe = ? and time >= ? and time <= ?
            ''',
            (account_id, symbol, timeframe, start_at, end_at),
        ).fetchone()

    if coverage is None:
        return False

    min_time, max_time, row_count = coverage
    return bool(min_time) and bool(max_time) and min_time <= start_at and max_time >= end_at and row_count > 0


def _get_runtime_account(account_id: str) -> dict:
    from python_service.app.quant.runtime import get_account_by_id

    return get_account_by_id(account_id)


def _normalize_iso_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat()


def _normalize_range_bounds(start_at: str, end_at: str, timeframe: Timeframe) -> tuple[str, str]:
    return _align_time_to_bucket(start_at, timeframe), _align_time_to_bucket(end_at, timeframe)


def _align_time_to_bucket(value: str, timeframe: Timeframe) -> str:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    timeframe_seconds = TIMEFRAME_SECONDS[timeframe]
    aligned_timestamp = int(parsed.timestamp()) // timeframe_seconds * timeframe_seconds
    return datetime.fromtimestamp(aligned_timestamp, timezone.utc).isoformat()

