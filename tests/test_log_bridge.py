from __future__ import annotations

import logging
from unittest import TestCase

from app.gui.log_bridge import QtLogBridge


class QtLogBridgeTests(TestCase):
    _LOGGER_PREFIX = "icstex.test_log_bridge"

    def setUp(self) -> None:
        self._logger_index = 0

    def _unique_logger_name(self) -> str:
        self._logger_index += 1
        return f"{self._LOGGER_PREFIX}.{id(self)}.{self._logger_index}"

    def test_install_on_attaches_handler_and_emits_signal(self) -> None:
        logger_name = self._unique_logger_name()
        bridge = QtLogBridge()
        received: list[tuple[str, int, str]] = []
        bridge.messageEmitted.connect(lambda name, level, message: received.append((name, level, message)))

        bridge.install_on(logger_name, level=logging.DEBUG)
        logger = logging.getLogger(logger_name)
        logger.info("hello")

        self.assertEqual(received, [(logger_name, logging.INFO, "hello")])
        self.assertIn(bridge.handler, logger.handlers)

    def test_install_on_is_idempotent(self) -> None:
        logger_name = self._unique_logger_name()
        bridge = QtLogBridge()
        bridge.install_on(logger_name)
        bridge.install_on(logger_name)

        logger = logging.getLogger(logger_name)
        attached = [handler for handler in logger.handlers if handler is bridge.handler]
        self.assertEqual(len(attached), 1)

    def test_install_on_lowers_logger_level_when_needed(self) -> None:
        logger_name = self._unique_logger_name()
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)
        bridge = QtLogBridge()

        bridge.install_on(logger_name, level=logging.INFO)

        self.assertLessEqual(logger.level, logging.INFO)

    def test_uninstall_removes_handler_and_stops_emissions(self) -> None:
        logger_name = self._unique_logger_name()
        bridge = QtLogBridge()
        received: list[str] = []
        bridge.messageEmitted.connect(lambda _name, _level, message: received.append(message))

        bridge.install_on(logger_name)
        logger = logging.getLogger(logger_name)
        logger.info("before")

        bridge.uninstall()
        logger.info("after")

        self.assertEqual(received, ["before"])
        self.assertNotIn(bridge.handler, logger.handlers)

    def test_uninstall_is_safe_when_not_installed(self) -> None:
        bridge = QtLogBridge()
        bridge.uninstall()  # should not raise
        bridge.uninstall()
