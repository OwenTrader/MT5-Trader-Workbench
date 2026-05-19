from python_service.app.local_copy_trading.models import LocalCopyTradingState


def get_source_positions(state: LocalCopyTradingState) -> list[dict]:
    positions: list[dict] = []
    for account in state.source_accounts:
        if not account.is_active or account.connection_type != 'simulated':
            continue
        positions.append({
            'position_id': f'{account.id}-sample-position',
            'source_account_id': account.id,
            'symbol': 'XAUUSD',
        })
    return positions
