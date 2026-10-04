"""Idempotent copy and close actions.

This is the layer that makes a copy action safe to retry. Before an order is
sent, the intent is written to SQLite keyed by ``<relationship>:<source
position>``. The key is unique, so a retry after a crash finds the existing row
instead of opening a second position.

``engine.process_tick`` talks to these functions and knows nothing about
persistence or connections.

Two things happen here that deliberately do not happen in the pure engine:

* Pre-trade guards read live follower state (margin level, open positions), so
  they need the connection that is about to place the order.
* Volume reconciliation needs the follower's *actual* position size, which is
  only knowable from the terminal.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from python_service.app.local_copy_trading import copy_trading_db, follower_executor, guards, volume_planner
from python_service.app.local_copy_trading.models import (
    CopyRelationship,
    CopyResult,
    CopyTradingRiskSettings,
    FollowerAccount,
    SyncEvent,
)
from python_service.app.local_copy_trading.runtime import utc_now_iso
from python_service.app.services.mt5_session import Mt5SessionError, use_account


logger = logging.getLogger(__name__)


# MT5 deal entry directions that close (fully or partly) a position.
_DEAL_ENTRY_OUT = 1
_DEAL_ENTRY_OUT_BY = 3


def build_client_key(relationship_id: str, source_position_id: str) -> str:
    """Identity of one source position copied through one relationship."""
    return f'{relationship_id}:{source_position_id}'


def _source_volume(source_position: dict) -> float:
    return float(source_position.get('volume') or 0)


def _daily_realized_profit(client) -> float:
    """Sum today's closed-deal result (profit + commission + swap) for the account.

    Returns 0.0 when the terminal cannot answer, because a guard that cannot
    read its input must not turn into a hard failure of the copy path.
    """
    history_get = getattr(client, 'history_deals_get', None)
    if history_get is None:
        return 0.0

    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        deals = history_get(day_start, now)
    except Exception:
        return 0.0

    total = 0.0
    for deal in deals or []:
        if int(getattr(deal, 'entry', 1) or 1) not in (_DEAL_ENTRY_OUT, _DEAL_ENTRY_OUT_BY):
            continue
        total += float(getattr(deal, 'profit', 0) or 0)
        total += float(getattr(deal, 'commission', 0) or 0)
        total += float(getattr(deal, 'swap', 0) or 0)
    return total


def _guard_decision(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    *,
    planned_volume: float,
    settings: CopyTradingRiskSettings | None,
    daily_open_count: int,
    daily_realized_profit: float,
    consecutive_failures: int,
):
    """Evaluate the configured limits against live follower state."""
    if settings is None:
        return guards.GuardDecision(True)

    account_info = None
    positions: list[dict] = []
    if client is not None:
        raw_account_info = client.account_info()
        if raw_account_info is not None:
            account_info = follower_executor.as_dict(raw_account_info)
        positions = follower_executor.list_positions(client)

    # A caller that knows the realised result passes it; the trading loop does
    # not track it, so it is read from the terminal's deal history here.
    if daily_realized_profit == 0.0 and settings.max_daily_loss > 0 and client is not None:
        daily_realized_profit = _daily_realized_profit(client)

    return guards.evaluate_open_guard(
        relationship,
        planned_volume=planned_volume,
        follower_account_info=account_info,
        follower_positions=positions,
        settings=settings,
        daily_open_count=daily_open_count,
        daily_realized_profit=daily_realized_profit,
        consecutive_failures=consecutive_failures,
    )


def _sync_existing_position(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
    *,
    client_key: str,
    existing: dict,
    db_path: Path | str,
) -> CopyResult:
    """Bring an already-copied follower position in line with the source size.

    The source ticket survives a partial close and a scale in, so reaching this
    branch means the position is still open but may no longer be the right size.
    A source volume identical to the last one we acted on short-circuits without
    sending anything.
    """
    follower_position_id = existing['follower_position_ticket'] or ''
    follower_order_id = existing['follower_order_id'] or ''
    if client is None:
        return CopyResult(
            True,
            'copied',
            f"Already copied as follower position {follower_position_id or follower_order_id}",
            follower_position_id,
            follower_order_id,
        )

    symbol = relationship.follower_symbol
    try:
        if not client.symbol_select(symbol, True):
            return CopyResult(
                False,
                'failed',
                f'Failed to select follower symbol {symbol}. Error: {client.last_error()}',
                follower_position_id,
                follower_order_id,
            )
        symbol_info = client.symbol_info(symbol)
        if symbol_info is None:
            return CopyResult(
                False,
                'failed',
                f'Missing symbol info for follower symbol {symbol}. Error: {client.last_error()}',
                follower_position_id,
                follower_order_id,
            )

        owned = follower_executor.find_owned_position(
            client,
            symbol,
            relationship_id=relationship.id,
            position_id=existing['source_position_id'],
        )
        if owned is None:
            message = f'Drift: follower position for source position {existing["source_position_id"]} is missing'
            copy_trading_db.mark_drifted(
                client_key,
                message=message,
                updated_at=utc_now_iso(),
                db_path=db_path,
            )
            logger.warning(
                'Relationship %s source position %s: %s',
                relationship.id,
                existing['source_position_id'],
                message,
            )
            return CopyResult(False, 'failed', message, follower_position_id, follower_order_id, code='drift_missing')

        follower_equity = None
        if relationship.volume_mode == 'equity_ratio':
            account_info = client.account_info()
            if account_info is not None:
                follower_equity = float(getattr(account_info, 'equity', 0) or 0)

        expected_volume = volume_planner.plan_volume(
            relationship,
            source_position,
            symbol_info=symbol_info,
            source_equity=source_position.get('source_equity'),
            follower_equity=follower_equity,
        )
    except ValueError as error:
        return CopyResult(False, 'failed', str(error), follower_position_id, follower_order_id)

    success, message = follower_executor.adjust_copied_position_volume(
        client,
        follower,
        relationship,
        source_position,
        expected_volume=expected_volume,
    )

    # The source volume is only recorded on success: recording it for a
    # rejected adjustment would tell the engine the sizes already match, and
    # the drift would never be retried.
    if not success:
        copy_trading_db.mark_failed(
            client_key,
            message=message,
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
        logger.warning(
            'Relationship %s source position %s: volume sync failed: %s',
            relationship.id,
            existing['source_position_id'],
            message,
        )
        return CopyResult(False, 'failed', message, follower_position_id, follower_order_id, code='volume_sync_failed')

    copy_trading_db.confirm_order(
        client_key,
        follower_position_ticket=follower_position_id,
        follower_order_id=follower_order_id,
        message=message,
        updated_at=utc_now_iso(),
        db_path=db_path,
    )
    copy_trading_db.record_source_volume(
        client_key,
        source_volume=_source_volume(source_position),
        updated_at=utc_now_iso(),
        db_path=db_path,
    )
    logger.info(
        'Relationship %s source position %s: %s',
        relationship.id,
        existing['source_position_id'],
        message,
    )
    return CopyResult(True, 'copied', message, follower_position_id, follower_order_id, code='volume_synced')


def execute_copy(
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
    *,
    db_path: Path | str | None = None,
    risk_settings: CopyTradingRiskSettings | None = None,
    daily_open_count: int = 0,
    daily_realized_profit: float = 0.0,
    consecutive_failures: int = 0,
) -> CopyResult:
    """Copy one source position, at most once, ever.

    Passing ``risk_settings`` enables the pre-trade guards; leaving it as None
    keeps the previous behaviour of sending the order unconditionally.
    """
    source_position_id = str(source_position.get('position_id') or source_position.get('ticket') or '')
    if not source_position_id:
        return CopyResult(False, 'failed', 'Source position has no identifier')

    client_key = build_client_key(relationship.id, source_position_id)
    existing = copy_trading_db.find_by_client_key(client_key, db_path=db_path)
    # A row carrying a follower ticket means a follower position may still be
    # open even when the last action on it failed; such a row must be synced,
    # never re-placed as a second independent order for the same source ticket.
    open_existing = existing is not None and (
        existing['status'] == 'confirmed' or bool(existing.get('follower_position_ticket'))
    )

    # A confirmed row that still matches the source size is already done. A
    # confirmed row whose source size moved needs the follower adjusted, and
    # that only makes sense with a live connection.
    if open_existing and float(existing['source_volume'] or 0) == _source_volume(source_position):
        return CopyResult(
            True,
            'copied',
            f"Already copied as follower position {existing['follower_position_ticket'] or existing['follower_order_id']}",
            existing['follower_position_ticket'] or '',
            existing['follower_order_id'] or '',
        )

    copy_trading_db.insert_pending(
        client_key=client_key,
        relationship_id=relationship.id,
        source_account_id=relationship.source_account_id,
        follower_account_id=relationship.follower_account_id,
        source_position_id=source_position_id,
        created_at=utc_now_iso(),
        db_path=db_path,
    )

    if follower.connection_type != 'mt5_terminal':
        if open_existing:
            return _sync_existing_position(
                None,
                follower,
                relationship,
                source_position,
                client_key=client_key,
                existing=existing,
                db_path=db_path,
            )
        result = follower_executor.copy_position_to_follower(None, follower, relationship, source_position)
        return _settle(client_key, result, source_position, db_path)

    try:
        with use_account(
            follower.terminal_path,
            follower.login,
            follower.password,
            follower.server,
        ) as client:
            if open_existing:
                return _sync_existing_position(
                    client,
                    follower,
                    relationship,
                    source_position,
                    client_key=client_key,
                    existing=existing,
                    db_path=db_path,
                )

            return _place_order(
                client,
                follower,
                relationship,
                source_position,
                client_key=client_key,
                db_path=db_path,
                risk_settings=risk_settings,
                daily_open_count=daily_open_count,
                daily_realized_profit=daily_realized_profit,
                consecutive_failures=consecutive_failures,
            )
    except Mt5SessionError as error:
        copy_trading_db.mark_failed(
            client_key,
            message=str(error),
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
        logger.error('Relationship %s source position %s: session error: %s', relationship.id, source_position_id, error)
        return CopyResult(False, 'failed', str(error), code='session_error')


def _place_order(
    client,
    follower: FollowerAccount,
    relationship: CopyRelationship,
    source_position: dict,
    *,
    client_key: str,
    db_path: Path | str,
    risk_settings: CopyTradingRiskSettings | None,
    daily_open_count: int,
    daily_realized_profit: float,
    consecutive_failures: int,
) -> CopyResult:
    """Place a new follower order, guarding it when limits are configured.

    Without settings there is nothing to decide, so the executor's combined call
    is used directly and nothing reaches the broker later than before. With
    settings the order is planned first, because every limit is expressed in
    terms of the size being placed.
    """
    if risk_settings is None:
        result = follower_executor.copy_position_to_follower(client, follower, relationship, source_position)
        return _settle(client_key, result, source_position, db_path)

    plan = follower_executor.plan_copy_order(client, follower, relationship, source_position)
    if plan.short_circuit is None and plan.ok:
        decision = _guard_decision(
            client,
            follower,
            relationship,
            planned_volume=plan.volume,
            settings=risk_settings,
            daily_open_count=daily_open_count,
            daily_realized_profit=daily_realized_profit,
            consecutive_failures=consecutive_failures,
        )
        if not decision.allowed:
            copy_trading_db.mark_skipped(
                client_key,
                message=decision.message,
                updated_at=utc_now_iso(),
                db_path=db_path,
            )
            logger.info(
                'Relationship %s source position %s: guard %s refused the copy: %s',
                relationship.id,
                source_position.get('position_id') or source_position.get('ticket') or '',
                decision.rule,
                decision.message,
            )
            return CopyResult(False, 'skipped', decision.message, code=f'guard.{decision.rule}')

    result = follower_executor.send_copy_order(client, follower, relationship, plan, source_position)
    return _settle(client_key, result, source_position, db_path)


def _settle(
    client_key: str,
    result: tuple,
    source_position: dict,
    db_path: Path | str,
) -> CopyResult:
    """Write the order-map row to match an executor result."""
    success, message, follower_position_id, follower_order_id = result

    if success:
        copy_trading_db.confirm_order(
            client_key,
            follower_position_ticket=follower_position_id,
            follower_order_id=follower_order_id,
            message=message,
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
        copy_trading_db.record_source_volume(
            client_key,
            source_volume=_source_volume(source_position),
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
        logger.info('%s', message)
    else:
        copy_trading_db.mark_failed(
            client_key,
            message=message,
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
        logger.warning('Copy %s failed: %s', client_key, message)

    return CopyResult(
        bool(success),
        'copied' if success else 'failed',
        message,
        follower_position_id,
        follower_order_id,
        code='copy_ok' if success else 'copy_failed',
    )


def execute_close(
    follower: FollowerAccount,
    relationship: CopyRelationship,
    copied_event: SyncEvent,
    *,
    db_path: Path | str | None = None,
) -> tuple[bool, str]:
    """Close a copied follower position and settle its order-map row."""
    if follower.connection_type == 'mt5_terminal':
        try:
            with use_account(
                follower.terminal_path,
                follower.login,
                follower.password,
                follower.server,
            ) as client:
                success, message = follower_executor.close_copied_position_on_follower(
                    client, follower, relationship, copied_event
                )
        except Mt5SessionError as error:
            success, message = False, str(error)
    else:
        success, message = follower_executor.close_copied_position_on_follower(
            None, follower, relationship, copied_event
        )

    if success:
        copy_trading_db.mark_closed(
            build_client_key(relationship.id, copied_event.position_id),
            message=message,
            updated_at=utc_now_iso(),
            db_path=db_path,
        )
        logger.info('Relationship %s source position %s: %s', relationship.id, copied_event.position_id, message)
    else:
        logger.warning(
            'Relationship %s source position %s: close failed: %s',
            relationship.id,
            copied_event.position_id,
            message,
        )
    return success, message
