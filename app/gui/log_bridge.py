from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal


class QtLogBridge(QObject):
    """A logging.Handler that emits Qt signals so log records can update widgets safely.

    Qt's signal/slot machinery marshals messages back to the main thread, which
    makes it safe to call ``logger.info(...)`` from a worker thread and still
    update a ``QTextEdit`` without using ``QMetaObject.invokeMethod`` directly.
    """

    messageEmitted = Signal(str, int, str)  # name, levelno, formatted message

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._handler = _SignalEmittingHandler(self)
        self._installed_loggers: list[logging.Logger] = []

    def install_on(self, logger_name: str, level: int = logging.INFO) -> None:
        logger = logging.getLogger(logger_name)
        if level < logger.level or logger.level == logging.NOTSET:
            logger.setLevel(level)
        if self._handler not in logger.handlers:
            logger.addHandler(self._handler)
            self._installed_loggers.append(logger)

    def uninstall(self) -> None:
        for logger in self._installed_loggers:
            logger.removeHandler(self._handler)
        self._installed_loggers.clear()

    @property
    def handler(self) -> logging.Handler:
        return self._handler


class _SignalEmittingHandler(logging.Handler):
    def __init__(self, bridge: QtLogBridge) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter("%(message)s"))
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:  # pragma: no cover - formatter robustness
            message = record.getMessage()
        self._bridge.messageEmitted.emit(record.name, record.levelno, message)
