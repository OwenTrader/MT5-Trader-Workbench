import json
from pathlib import Path

from python_service.app.local_copy_trading.models import LocalCopyTradingState


DEFAULT_STORAGE_PATH = Path('storage/local_copy_trading.json')


def load_state(storage_path: Path | str = DEFAULT_STORAGE_PATH) -> LocalCopyTradingState:
    path = Path(storage_path)
    if not path.exists():
        return LocalCopyTradingState()
    normalized_state = path.read_text(encoding='utf-8').strip('\ufeff\x00 \t\r\n')
    if not normalized_state:
        return LocalCopyTradingState()
    return LocalCopyTradingState(**json.loads(normalized_state))


def save_state(state: LocalCopyTradingState, storage_path: Path | str = DEFAULT_STORAGE_PATH) -> LocalCopyTradingState:
    path = Path(storage_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f'{path.suffix}.tmp')
    temp_path.write_text(json.dumps(state.model_dump(), ensure_ascii=False, indent=2), encoding='utf-8')
    temp_path.replace(path)
    return state
