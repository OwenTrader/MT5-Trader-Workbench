import json
from pathlib import Path

from python_service.app.quant.models import QuantJob
from python_service.app.quant.paths import get_jobs_path


DEFAULT_JOBS_PATH = get_jobs_path()


def load_jobs(storage_path: Path | str = DEFAULT_JOBS_PATH) -> list[QuantJob]:
    path = Path(storage_path)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding='utf-8'))
    return [QuantJob(**item) for item in payload]


def save_jobs(jobs: list[QuantJob], storage_path: Path | str = DEFAULT_JOBS_PATH) -> None:
    path = Path(storage_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f'{path.suffix}.tmp')
    temp_path.write_text(json.dumps([job.model_dump() for job in jobs], ensure_ascii=False, indent=2), encoding='utf-8')
    temp_path.replace(path)
