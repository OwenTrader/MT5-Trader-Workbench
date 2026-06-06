from python_service.app.local_copy_trading.models import LocalCopyTradingState
from python_service.app.services.mt5_service import init_mt5_account, mt5, mt5_connection_lock, shutdown_mt5


def _as_dict(value) -> dict:
    if hasattr(value, '_asdict'):
        return value._asdict()
    if isinstance(value, dict):
        return value
    return dict(value)


def get_source_positions(state: LocalCopyTradingState) -> list[dict]:
    positions: list[dict] = []
    source_account_ids = {
        relationship.source_account_id
        for relationship in state.relationships
        if relationship.is_active
    }

    for account in state.accounts:
        if account.id not in source_account_ids:
            continue
        if not account.is_active:
            continue
        if account.connection_type == 'simulated':
            positions.append({
                'position_id': f'{account.id}-sample-position',
                'source_account_id': account.id,
                'symbol': 'XAUUSD',
            })
            continue
        if account.connection_type != 'mt5_terminal':
            continue

        with mt5_connection_lock():
            success, detail = init_mt5_account(account.terminal_path, account.login, account.password, account.server)
            if not success:
                raise RuntimeError(detail or f'Failed to connect source account {account.name}')

            try:
                for position in mt5.positions_get() or []:
                    payload = _as_dict(position)
                    payload['source_account_id'] = account.id
                    payload['position_id'] = str(payload.get('ticket') or payload.get('identifier') or '')
                    positions.append(payload)
            finally:
                shutdown_mt5()
    return positions
