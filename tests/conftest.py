import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))

import customtkinter as ctk  # noqa: E402
import db  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Redirige db.app_root() vers un dossier temporaire pour isoler chaque test."""
    monkeypatch.setattr(db, "app_root", lambda: tmp_path)
    db.init_db()
    yield db


@pytest.fixture(scope="session")
def root():
    """Unique fenêtre Tk racine pour toute la suite — partagée par tous les modules qui pilotent
    de vrais widgets CustomTkinter (test_case_tab_*.py) : CustomTkinter ne supporte correctement
    qu'une seule fenêtre Tk par processus (son suivi global du scaling/thème se corrompt si on en
    recrée une seconde), donc jamais un `ctk.CTk()` par module."""
    r = ctk.CTk()
    yield r
    r.destroy()
