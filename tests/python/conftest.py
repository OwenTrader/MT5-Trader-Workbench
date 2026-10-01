from pathlib import Path
import sys
import pytest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Keep every test out of the repo working directory.

    Several services persist to CWD-relative paths under storage/ (some of
    those files are git-tracked); without this a test run dirties the tree.
    Tests needing repo-relative fixtures must build paths from ROOT instead.
    """
    monkeypatch.chdir(tmp_path)
