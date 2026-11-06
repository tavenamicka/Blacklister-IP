"""Identité de l'appli pour l'écran 'À propos' : version, date de build, auteur/contact.

En exécutable buildé (`./build.ps1`), version et date viennent de `_build_info.py`, généré au
moment du build (git describe + date du jour) et embarqué par PyInstaller comme un module normal.
En dev (`python app/main.py`, pas de build), `_build_info.py` n'existe pas : la version est alors
recalculée à la volée depuis git, et la date de build n'a pas de sens (pas de build)."""
import subprocess
from pathlib import Path

APP_NAME = "Blacklister IP"
AUTHOR = "Mickael Tavenart"
CONTACT = "mickael.tavenart@gmail.com"
COPYRIGHT = "© 2026 Mickael Tavenart"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _git_version() -> str:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            capture_output=True, text=True, timeout=3, cwd=_repo_root(),
        )
    except (OSError, subprocess.SubprocessError):
        return "dev"
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "dev"


def get_version() -> str:
    try:
        from _build_info import VERSION
        return VERSION
    except ImportError:
        return _git_version()


def get_build_date() -> str:
    try:
        from _build_info import BUILD_DATE
        return BUILD_DATE
    except ImportError:
        return "non buildé (mode développement)"
