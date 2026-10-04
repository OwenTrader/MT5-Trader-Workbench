"""Pre-trade guards for copy actions.

A guard answers one question: should this copy be allowed to reach the broker?
Every rule is optional and disabled by default (a limit of 0 means "no limit"),
so an unconfigured install behaves exactly as it did before this module existed.

Guards run *before* the order is sent and *after* the volume has been planned,
because several rules need to know the size of the order being placed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from python_service.app.local_copy_trading.models import CopyRelationship, CopyTradingRiskSettings


from python_service.app.services.storage_paths import copy_trading_risk_file


@dataclass(frozen=True)
class GuardDecision:
    """Outcome of a guard evaluation.

    ``rule`` is a stable identifier so the UI and tests can assert on the
    specific rule that fired instead of parsing a message.
    """

    allowed: bool
    rule: str = ''
    message: str = ''


def load_risk_settings(path: Path | str | None = None) -> CopyTradingRiskSettings:
    if path is None:
        path = copy_trading_risk_file()
    settings_path = Path(path)
    if not settings_path.exists():
        return CopyTradingRiskSettings()
    raw = settings_path.read_text(encoding='utf-8').strip('\ufeff\x00 \t\r\n')
    if not raw:
        return CopyTradingRiskSettings()
    return CopyTradingRiskSettings(**json.loads(raw))


def save_risk_settings(settings: CopyTradingRiskSettings, path: Path | str | None = None) -> None:
    if path is None:
        path = copy_trading_risk_file()
    settings_path = Path(path)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings.model_dump(), ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def _symbol_positions(follower_positions: list[dict], symbol: str) -> list[dict]:
    target = str(symbol or '').strip().casefold()
    return [
        position
        for position in follower_positions
        if str(position.get('symbol') or '').strip().casefold() == target
    ]


def evaluate_open_guard(
    relationship: CopyRelationship,
    *,
    planned_volume: float,
    follower_account_info: dict | None,
    follower_positions: list[dict],
    settings: CopyTradingRiskSettings,
    daily_open_count: int = 0,
    daily_realized_profit: float = 0.0,
    consecutive_failures: int = 0,
) -> GuardDecision:
    """Decide whether this copy may proceed.

    Returns an allowed decision unless a configured limit is breached. The first
    breach wins; rules are ordered from "the account is already in trouble" to
    "this specific order is too big".
    """
    if settings.max_consecutive_failures > 0 and consecutive_failures >= settings.max_consecutive_failures:
        return GuardDecision(
            False,
            'consecutive_failures',
            f'Relationship has failed {consecutive_failures} times in a row (limit {settings.max_consecutive_failures})',
        )

    if settings.max_daily_open_count > 0 and daily_open_count >= settings.max_daily_open_count:
        return GuardDecision(
            False,
            'daily_open_count',
            f'Daily open count {daily_open_count} reached the limit of {settings.max_daily_open_count}',
        )

    if settings.max_daily_loss > 0 and daily_realized_profit <= -abs(settings.max_daily_loss):
        return GuardDecision(
            False,
            'daily_loss',
            f'Daily realised result {daily_realized_profit:.2f} reached the loss limit of {settings.max_daily_loss}',
        )

    if follower_account_info and settings.min_margin_level > 0:
        margin_level = follower_account_info.get('margin_level')
        if margin_level is not None and float(margin_level) < settings.min_margin_level:
            return GuardDecision(
                False,
                'margin_level',
                f'Follower margin level {margin_level} is below the required {settings.min_margin_level}',
            )

    symbol = relationship.follower_symbol
    existing = _symbol_positions(follower_positions, symbol)

    if settings.max_positions_per_symbol > 0 and len(existing) >= settings.max_positions_per_symbol:
        return GuardDecision(
            False,
            'max_positions_per_symbol',
            f'{symbol} already holds {len(existing)} positions (limit {settings.max_positions_per_symbol})',
        )

    if settings.max_volume_per_symbol > 0:
        held_volume = sum(float(position.get('volume') or 0) for position in existing)
        if held_volume + planned_volume > settings.max_volume_per_symbol:
            return GuardDecision(
                False,
                'max_volume_per_symbol',
                f'{symbol} would hold {held_volume + planned_volume:.2f} lots (limit {settings.max_volume_per_symbol})',
            )

    return GuardDecision(True)
