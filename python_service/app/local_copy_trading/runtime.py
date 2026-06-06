from __future__ import annotations

import uuid
from datetime import datetime, timezone

from python_service.app.local_copy_trading.models import (
    Account,
    CopyRelationship,
    LocalCopyTradingState,
    SyncEvent,
)


_state = LocalCopyTradingState()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_state() -> LocalCopyTradingState:
    return _state


def reset_state(state: LocalCopyTradingState | None = None) -> LocalCopyTradingState:
    global _state
    _state = state or LocalCopyTradingState()
    return _state


def set_state(state: LocalCopyTradingState) -> LocalCopyTradingState:
    global _state
    _state = state
    return _state


def update_last_error(state: LocalCopyTradingState, error: str | None) -> LocalCopyTradingState:
    state.last_error = error
    return state


def update_runtime_settings(
    state: LocalCopyTradingState,
    *,
    enabled: bool | None = None,
    poll_interval_seconds: float | None = None,
) -> LocalCopyTradingState:
    if enabled is not None:
        state.enabled = enabled
    if poll_interval_seconds is not None:
        state.poll_interval_seconds = max(poll_interval_seconds, 0.5)
    return state


def _ensure_id(value: str) -> str:
    return value or str(uuid.uuid4())


def add_account(state: LocalCopyTradingState, account: Account) -> LocalCopyTradingState:
    state.accounts.append(account.model_copy(update={'id': _ensure_id(account.id)}))
    return state


def update_account(state: LocalCopyTradingState, account_id: str, account: Account) -> LocalCopyTradingState:
    for index, current in enumerate(state.accounts):
        if current.id == account_id:
            state.accounts[index] = account.model_copy(update={'id': account_id})
            return state
    raise ValueError('Account not found')


def add_relationship(state: LocalCopyTradingState, relationship: CopyRelationship) -> LocalCopyTradingState:
    if relationship.source_account_id == relationship.follower_account_id:
        raise ValueError('Source and follower accounts must be different')

    source_exists = any(account.id == relationship.source_account_id for account in state.accounts)
    follower_exists = any(account.id == relationship.follower_account_id for account in state.accounts)
    if not source_exists or not follower_exists:
        raise ValueError('Relationship must reference existing source and follower accounts')
    duplicate_exists = any(
        item.source_account_id == relationship.source_account_id
        and item.follower_account_id == relationship.follower_account_id
        and item.source_symbol == relationship.source_symbol
        and item.follower_symbol == relationship.follower_symbol
        for item in state.relationships
    )
    if duplicate_exists:
        raise ValueError('Relationship already exists for this source, follower, and symbol mapping')
    state.relationships.append(relationship.model_copy(update={'id': _ensure_id(relationship.id)}))
    return state


def remove_account(state: LocalCopyTradingState, account_id: str) -> LocalCopyTradingState:
    state.accounts = [account for account in state.accounts if account.id != account_id]
    removed_relationship_ids = {
        relationship.id
        for relationship in state.relationships
        if relationship.source_account_id == account_id or relationship.follower_account_id == account_id
    }
    state.relationships = [
        relationship
        for relationship in state.relationships
        if relationship.source_account_id != account_id and relationship.follower_account_id != account_id
    ]
    state.events = [
        event
        for event in state.events
        if event.source_account_id != account_id
        and event.follower_account_id != account_id
        and event.relationship_id not in removed_relationship_ids
    ]
    return state


def remove_relationship(state: LocalCopyTradingState, relationship_id: str) -> LocalCopyTradingState:
    state.relationships = [relationship for relationship in state.relationships if relationship.id != relationship_id]
    state.events = [event for event in state.events if event.relationship_id != relationship_id]
    return state


def add_event(state: LocalCopyTradingState, event: SyncEvent) -> LocalCopyTradingState:
    state.events.append(event.model_copy(update={'id': _ensure_id(event.id)}))
    return state


def has_copied_position(
    state: LocalCopyTradingState,
    *,
    relationship_id: str,
    source_account_id: str,
    follower_account_id: str,
    position_id: str,
) -> bool:
    return any(
        event.relationship_id == relationship_id
        and event.source_account_id == source_account_id
        and event.follower_account_id == follower_account_id
        and event.position_id == position_id
        and event.status == 'copied'
        for event in state.events
    )


def get_open_copied_events(state: LocalCopyTradingState) -> list[SyncEvent]:
    closed_keys = {
        (event.relationship_id, event.source_account_id, event.follower_account_id, event.position_id)
        for event in state.events
        if event.status == 'closed'
    }
    return [
        event
        for event in state.events
        if event.status == 'copied'
        and (event.relationship_id, event.source_account_id, event.follower_account_id, event.position_id) not in closed_keys
    ]


def build_overview(state: LocalCopyTradingState) -> dict:
    return {
        'runtime': {
            'enabled': state.enabled,
            'poll_interval_seconds': state.poll_interval_seconds,
            'last_error': state.last_error,
            'last_checked_at': state.last_checked_at,
        },
        'accounts': [account.model_dump() for account in state.accounts],
        'relationships': [relationship.model_dump() for relationship in state.relationships],
        'events': [event.model_dump() for event in state.events],
    }
