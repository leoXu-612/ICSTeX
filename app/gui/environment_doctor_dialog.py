from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QPushButton, QTextEdit, QVBoxLayout

from app.core.diagnostics import Diagnostic
from app.core.environment_doctor import EnvironmentReport, FeedbackMetadata, build_feedback_bundle


FeedbackContextProvider = Callable[[], "FeedbackContext"]


class FeedbackContext:
    """Snapshot of data the feedback bundle can include.

    All fields are optional. The dialog only adds sections that are present,
    so this stays useful even when there is no open project or compile log.
    """

    def __init__(
        self,
        *,
        recent_log: str | None = None,
        diagnostics: Sequence[Diagnostic] | None = None,
        project_file: Path | str | None = None,
        metadata: FeedbackMetadata | None = None,
    ) -> None:
        self.recent_log = recent_log
        self.diagnostics = tuple(diagnostics) if diagnostics else ()
        self.project_file = project_file
        self.metadata = metadata


class EnvironmentDoctorDialog(QDialog):
    def __init__(
        self,
        report: EnvironmentReport,
        parent=None,  # type: ignore[no-untyped-def]
        *,
        feedback_context_provider: FeedbackContextProvider | None = None,
    ) -> None:
        super().__init__(parent)
        self.report = report
        self._feedback_context_provider = feedback_context_provider
        self.setWindowTitle("环境医生")
        self.resize(720, 520)

        layout = QVBoxLayout(self)
        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setPlainText(report.as_text())
        layout.addWidget(self.report_view)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.copy_button = QPushButton("复制诊断报告")
        self.copy_button.setObjectName("primaryButton")
        buttons.addButton(self.copy_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.feedback_button = QPushButton("复制反馈包")
        self.feedback_button.setToolTip("包含环境信息、最近日志和项目检查摘要，不包含论文正文。")
        buttons.addButton(self.feedback_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        self.copy_button.clicked.connect(self.copy_report)
        self.feedback_button.clicked.connect(self.copy_feedback_bundle)
        layout.addWidget(buttons)

    def copy_report(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self.report.as_text())
        self.copy_button.setText("已复制")

    def copy_feedback_bundle(self) -> None:
        context = self._feedback_context_provider() if self._feedback_context_provider else FeedbackContext()
        bundle = build_feedback_bundle(
            self.report,
            recent_log=context.recent_log,
            diagnostics=context.diagnostics,
            project_file=context.project_file,
            metadata=context.metadata,
        )
        clipboard = QApplication.clipboard()
        clipboard.setText(bundle)
        self.feedback_button.setText("已复制反馈包")
