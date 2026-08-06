from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app import __app_name__


LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def log_directory() -> Path:
    """Pick a platform-appropriate directory for ICSTeX log files."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Logs" / __app_name__
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = Path(appdata) / __app_name__ / "logs" if appdata else Path.home() / f".{__app_name__.lower()}" / "logs"
    else:
        xdg = os.environ.get("XDG_STATE_HOME") or os.environ.get("XDG_CACHE_HOME")
        base = Path(xdg) / __app_name__ if xdg else Path.home() / ".local" / "state" / __app_name__
    return base


def configure_logging(level: int | str = logging.INFO, *, write_to_file: bool = True) -> Path | None:
    """Configure root logger once. Safe to call multiple times.

    Returns the log file path if a file handler was installed, otherwise None.
    """
    root = logging.getLogger()
    if getattr(root, "_icstex_configured", False):
        return getattr(root, "_icstex_log_path", None)

    root.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    log_path: Path | None = None
    if write_to_file:
        try:
            directory = log_directory()
            directory.mkdir(parents=True, exist_ok=True)
            log_path = directory / f"{__app_name__.lower()}.log"
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError:
            log_path = None

    root._icstex_configured = True  # type: ignore[attr-defined]
    root._icstex_log_path = log_path  # type: ignore[attr-defined]
    return log_path


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
