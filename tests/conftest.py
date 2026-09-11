import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))

import pytest  # noqa: E402

import db  # noqa: E402


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Redirige db.app_root() vers un dossier temporaire pour isoler chaque test."""
    monkeypatch.setattr(db, "app_root", lambda: tmp_path)
    db.init_db()
    yield db
