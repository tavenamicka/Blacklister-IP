"""Logging applicatif + capture des exceptions non gérées (utile en build --windowed, sans console)."""
import logging
import sys
import tkinter.messagebox as messagebox
from logging.handlers import RotatingFileHandler

from db import app_root

LOGGER_NAME = "blacklister"
MAX_LOG_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3


def setup_logging() -> logging.Logger:
    """Fichier tournant (1 Mo x 4) : évite qu'app.log grossisse sans limite sur une installation
    utilisée longtemps, sans dépendre d'une rotation externe (l'app est portable, sans logrotate)."""
    log_dir = app_root() / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger


def _log_and_notify(logger: logging.Logger, exc_type, exc_value, exc_tb) -> None:
    logger.critical("Erreur non gérée", exc_info=(exc_type, exc_value, exc_tb))
    try:
        messagebox.showerror(
            "Blacklister IP — erreur inattendue",
            f"Une erreur inattendue s'est produite :\n\n{exc_value}\n\n"
            "Le détail a été enregistré dans data/app.log.",
        )
    except Exception:
        pass


def install_global_handlers(logger: logging.Logger) -> None:
    """Capture les exceptions non gérées survenant hors boucle d'événements Tkinter (ex: au démarrage)."""

    def _excepthook(exc_type, exc_value, exc_tb):
        _log_and_notify(logger, exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook


def install_tk_handler(root, logger: logging.Logger) -> None:
    """Capture les exceptions levées dans les callbacks Tkinter (boutons, bindings) — Tkinter ne les
    laisse pas remonter à sys.excepthook, il faut surcharger report_callback_exception sur la fenêtre racine."""

    def _report_callback_exception(exc_type, exc_value, exc_tb):
        _log_and_notify(logger, exc_type, exc_value, exc_tb)

    root.report_callback_exception = _report_callback_exception
