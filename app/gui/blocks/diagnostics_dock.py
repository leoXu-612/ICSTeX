"""Compile diagnostics dock for the Block workspace (PREVIEW/FINAL/errors)."""
from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.blocks.source_map import block_at_line
from app.core.compiler import BuildPurpose, CompileOutcome
from app.gui.responsive.helpers import ButtonFlowLayout
from app.gui.blocks.project_session import ProjectSession
from PySide6.QtCore import Signal, Qt


_ERROR_LINE_RE = re.compile(r"([^:\s]+\.tex):(\d+):")
_OUTCOME_LABELS = {CompileOutcome.SUCCESS: "成功", CompileOutcome.STOPPED: "已停止",
    CompileOutcome.TIMEOUT: "超时", CompileOutcome.TOOLCHAIN_MISSING: "缺少编译工具",
    CompileOutcome.ROOT_FILE_MISSING: "入口文件缺失", CompileOutcome.PROCESS_START_FAILED: "启动失败",
    CompileOutcome.LATEX_ERROR: "LaTeX 错误", CompileOutcome.OUTPUT_MISSING: "未生成输出",
    CompileOutcome.INTERNAL_ERROR: "内部错误"}


class BlockDiagnostics(QWidget):
    """Shows compile state and lets the user jump to the offending Block."""

    error_seen = Signal()

    def __init__(self, session: ProjectSession, parent=None) -> None:
        super().__init__(parent)
        self.session = session
        self._last_result = None
        self.status_label = QLabel("空闲")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.locate_button = QPushButton("定位错误 Block")
        self.locate_button.setEnabled(False)
        self.locate_button.clicked.connect(self._locate_error_block)
        self.copy_button = QPushButton("复制上次构建信息")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self._copy_build_info)

        row = QHBoxLayout()
        row.addWidget(QLabel("状态："))
        row.addWidget(self.status_label, stretch=1)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.log_view)
        actions = ButtonFlowLayout()
        actions.addWidget(self.locate_button)
        actions.addWidget(self.copy_button)
        layout.addLayout(actions)

        session.compile_requested.connect(self._on_requested)
        session.compile_finished.connect(self._on_finished)
        session.save_state_changed.connect(self._on_save_state)
        self._on_save_state()

    def _on_save_state(self):
        if self.session.save_error:
            self.status_label.setText("保存受阻：内存草稿仍保留")
            self.log_view.setPlainText(self.session.save_error)
            self.error_seen.emit()

    def _on_requested(self, reason: str) -> None:
        self.status_label.setText("已请求快速预览；等待保存与草稿状态核对。" if self.session._compile_authorized else
                                  "尚未授权自动预览；首次编译需显式触发。")
        self.status_label.setToolTip(f"请求原因：{reason}")
        self._on_save_state()

    def _on_finished(self, result) -> None:
        self._last_result = result
        self.copy_button.setEnabled(True)
        outcome = getattr(result, "outcome", None)
        purpose = {BuildPurpose.FINAL: "正式编译", BuildPurpose.PREVIEW: "快速预览"}.get(
            getattr(result, "purpose", None), "编译类型未知")
        self.status_label.setText(
            f"{purpose} · {_OUTCOME_LABELS.get(outcome, '结果未知')} · {getattr(result, 'duration_seconds', 0):.1f} 秒"
        )
        if getattr(result, "ok", False):
            self.log_view.setPlainText("编译成功；请查看 PDF 确认版面。")
            self.locate_button.setEnabled(False)
            return
        combined = "\n".join(part for part in (getattr(result, "stdout", "") or "", getattr(result, "stderr", "") or "") if part)
        self.log_view.setPlainText(combined[-4000:])
        has_error = self._error_line() is not None
        self.locate_button.setEnabled(has_error)
        # A missing engine or failed process can have no parseable TeX line.
        # The now-collapsed dock must still expose that failure. User Stop is
        # not an error notification and should not open another panel.
        if outcome is not CompileOutcome.STOPPED:
            self.error_seen.emit()

    def _copy_build_info(self):
        result = self._last_result
        if result is not None:
            QApplication.clipboard().setText("\n".join(f"{name}: {getattr(result, name, '')}"
                for name in ("root_file", "build_id", "purpose", "outcome", "returncode", "duration_seconds")))

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
