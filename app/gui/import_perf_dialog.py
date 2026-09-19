"""Development-mode performance monitor for image drag-and-drop import.

Shows the last import transaction summaries plus global compile counters:
compile requested vs actually started vs coalesced, full index scans, and
per-stage durations. Read-only; it never mutates import state.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app.core.import_metrics import import_metrics


class ImportPerfDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("导入性能诊断")
        self.setMinimumSize(620, 420)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setStyleSheet("font-family: Menlo, monospace; font-size: 12px;")

        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self._refresh)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(refresh_button)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("最近导入事务与编译计数（数据来自 import_metrics）："))
        layout.addWidget(self.text, stretch=1)
        layout.addLayout(buttons)
        self._refresh()

    def _refresh(self) -> None:
        counts = import_metrics.global_counts()
        lines = [
            f"全局编译计数: requested={counts['compile_requested']} "
            f"started={counts['compile_started']}",
            "",
            "最近导入事务：",
        ]
        summaries = import_metrics.summaries()
        if not summaries:
            lines.append("（暂无记录）")
        for summary in reversed(summaries):
            stages = summary.get("stages", {})
            stage_text = " ".join(f"{name}={value}s" for name, value in stages.items())
            lines.extend(
                [
                    f"transaction={summary['transaction_id']}",
                    f"  compile requested={summary['compile_requested']} "
                    f"started={summary['compile_started']} "
                    f"coalesced={summary['compile_coalesced']} "
                    f"full_index_scans={summary['full_index_scans']} "
                    f"total={summary['total_seconds']}s",
                    f"  stages: {stage_text}",
                    "",
                ]
            )
        self.text.setPlainText("\n".join(lines))
