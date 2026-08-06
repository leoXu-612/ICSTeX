from __future__ import annotations

import sys

from app.core.logging_config import configure_logging, get_logger


def main() -> int:
    configure_logging()
    logger = get_logger(__name__)
    try:
        from app.gui.main_window import run
    except ImportError as exc:
        logger.error("PySide6 is required to launch the desktop app.")
        logger.error("Install dependencies with: python3 -m pip install -r requirements.txt")
        logger.error("Import error: %s", exc)
        return 1

    return run(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
