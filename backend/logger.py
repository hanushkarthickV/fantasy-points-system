"""
Centralized logging configuration for the Fantasy Points System.

Usage in any module:
    from backend.logger import get_logger
    logger = get_logger(__name__)

Logs are written to both the console and a rotating log file at data/app.log.
"""

import logging
import logging.handlers
from pathlib import Path

from backend.config import DATA_DIR

LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "app.log"

_CONFIGURED = False

FORMAT = "%(asctime)s │ %(levelname)-7s │ %(name)-40s │ %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.DEBUG) -> None:
    """Configure root logger with console + file handlers. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(level)

    # ── Console Handler (INFO+) ────────────────────────────────────────────
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(FORMAT, datefmt=DATE_FMT))
    root.addHandler(console)

    # ── File Handler (DEBUG+, rotating 5 MB x 3 backups) ──────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FORMAT, datefmt=DATE_FMT))
    root.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("gspread").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)

    _CONFIGURED = True
    root.info("Logging initialised → console (INFO+) + file %s (DEBUG+)", LOG_FILE)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Ensures setup_logging() has been called."""
    setup_logging()
    return logging.getLogger(name)
