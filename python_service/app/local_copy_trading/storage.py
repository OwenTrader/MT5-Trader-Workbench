import json
from pathlib import Path

from python_service.app.services import secret_box

from python_service.app.local_copy_trading.models import LocalCopyTradingState


from python_service.app.services.storage_paths import copy_trading_state_file


def _default_storage_path() -> Path:
    return copy_trading_state_file()


def load_state(storage_path: Path | str | None = None) -> LocalCopyTradingState:
    path = Path(storage_path if storage_path is not None else _default_storage_path())
    if not path.exists():
        return LocalCopyTradingState()
    normalized_state = path.read_text(encoding='utf-8').strip('\ufeff\x00 \t\r\n')
    if not normalized_state:
        return LocalCopyTradingState()
    loaded = LocalCopyTradingState(**json.loads(normalized_state))
    loaded.accounts = [
        account.model_copy(update={'password': secret_box.decrypt(account.password) or ''})
        for account in loaded.accounts
    ]
    return loaded


def save_state(state: LocalCopyTradingState, storage_path: Path | str | None = None) -> LocalCopyTradingState:
    # Credentials are sealed with DPAPI at rest; the in-memory state keeps
    # plaintext for the session.
    sealed = state.model_copy(deep=True)
    sealed.accounts = [
        account.model_copy(update={'password': secret_box.encrypt(account.password) or ''})
        for account in state.accounts
    ]
    state = sealed
    path = Path(storage_path if storage_path is not None else _default_storage_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f'{path.suffix}.tmp')
    temp_path.write_text(json.dumps(state.model_dump(), ensure_ascii=False, indent=2), encoding='utf-8')
    temp_path.replace(path)
    return state
