"""Logging applicatif + capture des exceptions non gérées (utile en build --windowed, sans console)."""
import logging
import sys
import tkinter.messagebox as messagebox

from db import app_root

LOGGER_NAME = "blacklister"


def setup_logging() -> logging.Logger:
    log_dir = app_root() / "data"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "app.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    return logging.getLogger(LOGGER_NAME)


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
