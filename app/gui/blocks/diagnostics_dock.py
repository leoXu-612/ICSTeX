"""Compile diagnostics dock for the Block workspace (PREVIEW/FINAL/errors)."""
from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.source_map import block_at_line
from app.gui.blocks.project_session import ProjectSession


_ERROR_LINE_RE = re.compile(r"([^:\s]+\.tex):(\d+):")


class BlockDiagnostics(QWidget):
    """Shows compile state and lets the user jump to the offending Block."""

    def __init__(self, session: ProjectSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self._last_result = None
        self.status_label = QLabel("空闲")
        self.status_label.setWordWrap(True)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.locate_button = QPushButton("定位错误 Block")
        self.locate_button.setEnabled(False)
        self.locate_button.clicked.connect(self._locate_error_block)

        row = QHBoxLayout()
        row.addWidget(QLabel("状态："))
        row.addWidget(self.status_label, stretch=1)
        row.addWidget(self.locate_button)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.log_view)

        session.compile_requested.connect(lambda reason: self._on_requested(reason))
        session.compile_finished.connect(self._on_finished)

    def _on_requested(self, reason: str) -> None:
        self.status_label.setText(f"编译已排队：{reason}")

    def _on_finished(self, result) -> None:
        self._last_result = result
        outcome = getattr(result, "outcome", None)
        self.status_label.setText(
            f"完成：{getattr(result, 'purpose', '')} / {getattr(outcome, 'value', outcome)} "
            f"（{getattr(result, 'duration_seconds', 0):.1f}s）"
        )
        if getattr(result, "ok", False):
            self.log_view.setPlainText("编译成功，PDF 已刷新。")
            self.locate_button.setEnabled(False)
            return
        combined = "\n".join(part for part in (getattr(result, "stdout", "") or "", getattr(result, "stderr", "") or "") if part)
        self.log_view.setPlainText(combined[-4000:])
        self.locate_button.setEnabled(bool(self._error_line()))

    def _error_line(self) -> int | None:
        result = self._last_result
        if result is None:
            return None
        root_name = getattr(getattr(result, "root_file", None), "name", "main.tex")
        for part in (getattr(result, "stderr", "") or "", getattr(result, "stdout", "") or ""):
            for match in _ERROR_LINE_RE.finditer(part):
                if match.group(1) == root_name or match.group(1) == "main.tex":
                    return int(match.group(2))
        return None

    def _locate_error_block(self) -> None:
        result = self._last_result
        if result is None:
            return
        main_tex = getattr(result, "root_file", None)
        if main_tex is None or not main_tex.exists():
            return
        text = main_tex.read_text(encoding="utf-8", errors="replace")
        for part in (getattr(result, "stderr", "") or "", getattr(result, "stdout", "") or ""):
            for match in _ERROR_LINE_RE.finditer(part):
                line = int(match.group(2))
                mapping = block_at_line(text, line)
                if mapping is not None:
                    block_id = mapping.get("blockId")
                    if block_id:
                        self.session.selection.select_block(block_id, source="diagnostics")
                        return
