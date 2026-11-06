"""Tests de app_info.py — pas de vraie dépendance à un build réel : on simule la présence/absence
du module généré `_build_info.py` (cf. build.ps1) plutôt que d'en écrire un pour de vrai."""
import sys
import types

import app_info
import pytest


@pytest.fixture
def fake_build_info(monkeypatch):
    """Simule un exécutable buildé : un module `_build_info` avec VERSION/BUILD_DATE, comme
    build.ps1 le génère avant d'appeler PyInstaller."""
    module = types.ModuleType("_build_info")
    module.VERSION = "v1.0.0"
    module.BUILD_DATE = "2026-11-06"
    monkeypatch.setitem(sys.modules, "_build_info", module)
    yield module


@pytest.fixture
def no_build_info(monkeypatch):
    """Simule le mode dev (`python app/main.py`) : pas de `_build_info.py` généré."""
    monkeypatch.setitem(sys.modules, "_build_info", None)


def test_get_version_reads_build_info_when_present(fake_build_info):
    assert app_info.get_version() == "v1.0.0"


def test_get_build_date_reads_build_info_when_present(fake_build_info):
    assert app_info.get_build_date() == "2026-11-06"


def test_get_version_falls_back_to_git_in_dev_mode(no_build_info, monkeypatch):
    fake_result = types.SimpleNamespace(returncode=0, stdout="v1.0.0-2-gabcdef\n")
    monkeypatch.setattr(app_info.subprocess, "run", lambda *a, **k: fake_result)

    assert app_info.get_version() == "v1.0.0-2-gabcdef"


def test_get_version_falls_back_to_dev_when_git_unavailable(no_build_info, monkeypatch):
    def raise_oserror(*a, **k):
        raise OSError("git introuvable")

    monkeypatch.setattr(app_info.subprocess, "run", raise_oserror)

    assert app_info.get_version() == "dev"


def test_get_build_date_falls_back_to_dev_message(no_build_info):
    assert "développement" in app_info.get_build_date().lower()
