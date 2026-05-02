from pathlib import Path

import pytest

from python_service.app.services import awakening_service


def test_load_awakening_runtime_raises_clear_error_for_missing_scripts(monkeypatch):
    awakening_service._load_awakening_runtime.cache_clear()
    monkeypatch.setattr(awakening_service, "AWAKENING_SCRIPTS_DIR", Path("Z:/missing-awakening-scripts"))

    with pytest.raises(RuntimeError, match="Awakening scripts directory not found"):
        awakening_service._load_awakening_runtime()

    awakening_service._load_awakening_runtime.cache_clear()
