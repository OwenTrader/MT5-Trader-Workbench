from __future__ import annotations

import json
from pathlib import Path

from python_service.app.quant.models import QuantJobEvent
from python_service.app.quant.paths import get_events_path


DEFAULT_EVENTS_PATH = get_events_path()


def _resolve_storage_path(storage_path: Path | str | None) -> Path:
    return Path(DEFAULT_EVENTS_PATH if storage_path is None else storage_path)


def load_events(storage_path: Path | str | None = None) -> list[QuantJobEvent]:
    path = _resolve_storage_path(storage_path)
    if not path.exists():
        return []

    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, list):
        return []
    return [QuantJobEvent(**item) for item in payload if isinstance(item, dict)]


def save_events(events: list[QuantJobEvent], storage_path: Path | str | None = None) -> None:
    path = _resolve_storage_path(storage_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix('.tmp')
    temp_path.write_text(json.dumps([event.model_dump() for event in events], ensure_ascii=False, indent=2), encoding='utf-8')
    temp_path.replace(path)


def append_event(event: QuantJobEvent, storage_path: Path | str | None = None) -> QuantJobEvent:
    events = load_events(storage_path)
    events.append(event)
    save_events(events, storage_path)
    return event


def list_events(job_id: str, storage_path: Path | str | None = None, *, limit: int = 10) -> list[QuantJobEvent]:
    events = [event for event in load_events(storage_path) if event.job_id == job_id]
    events.sort(key=lambda event: event.created_at, reverse=True)
    return events[:limit]
