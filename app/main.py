"""Point d'entrée de l'application Blacklister IP."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db
import logging_setup
from ui import theme
from ui.main_window import MainWindow


def main():
    logger = logging_setup.setup_logging()
    logging_setup.install_global_handlers(logger)

    db.init_db()
    theme.apply()
    app = MainWindow()
    logging_setup.install_tk_handler(app, logger)
    app.mainloop()


if __name__ == "__main__":
    main()
