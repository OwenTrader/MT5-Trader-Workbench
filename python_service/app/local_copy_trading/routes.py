from fastapi import APIRouter, HTTPException

from python_service.app.local_copy_trading.models import CopyRelationship, FollowerAccount, LocalCopyTradingRuntimeUpdate, SourceAccount
from python_service.app.local_copy_trading.runtime import (
    add_follower_account,
    add_relationship,
    add_source_account,
    build_overview,
    get_state,
    remove_follower_account,
    remove_relationship,
    remove_source_account,
    reset_state,
    update_runtime_settings,
)
from python_service.app.local_copy_trading.storage import save_state
from python_service.app.services.mt5_service import verify_mt5_credentials


router = APIRouter(prefix='/local-copy-trading')


def _validate_account_connection(account: SourceAccount | FollowerAccount) -> None:
    is_valid, detail = verify_mt5_credentials(
        path=account.terminal_path,
        login=account.login,
        password=account.password,
        server=account.server,
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail=detail or 'Failed to verify MT5 account credentials')


def _ensure_runtime_can_enable() -> None:
    state = get_state()
    if not state.source_accounts or not state.follower_accounts or not state.relationships:
        raise HTTPException(
            status_code=400,
            detail='Add at least 1 source account, 1 follower account, and 1 relationship before enabling local copy trading',
        )


@router.get('')
def get_overview():
    return build_overview(get_state())


@router.post('/source-accounts')
def create_source_account(account: SourceAccount):
    _validate_account_connection(account)
    state = add_source_account(get_state(), account)
    save_state(state)
    return build_overview(state)


@router.post('/follower-accounts')
def create_follower_account(account: FollowerAccount):
    _validate_account_connection(account)
    state = add_follower_account(get_state(), account)
    save_state(state)
    return build_overview(state)


@router.post('/relationships')
def create_relationship(relationship: CopyRelationship):
    state = get_state()
    try:
        state = add_relationship(state, relationship)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    save_state(state)
    return build_overview(state)


@router.delete('/source-accounts/{account_id}')
def delete_source_account(account_id: str):
    state = remove_source_account(get_state(), account_id)
    save_state(state)
    return build_overview(state)


@router.delete('/follower-accounts/{account_id}')
def delete_follower_account(account_id: str):
    state = remove_follower_account(get_state(), account_id)
    save_state(state)
    return build_overview(state)


@router.delete('/relationships/{relationship_id}')
def delete_relationship(relationship_id: str):
    state = remove_relationship(get_state(), relationship_id)
    save_state(state)
    return build_overview(state)


@router.post('/runtime')
def update_runtime(payload: LocalCopyTradingRuntimeUpdate):
    if payload.enabled is True:
        _ensure_runtime_can_enable()

    state = update_runtime_settings(
        get_state(),
        enabled=payload.enabled,
        poll_interval_seconds=payload.poll_interval_seconds,
    )
    save_state(state)
    return build_overview(state)
