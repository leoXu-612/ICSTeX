from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.core.compiler import BuildPurpose, CompileManager
from app.gui.latex_editor import LaTeXEditor


SAMPLE_DOCUMENT = """\\documentclass{article}
\\usepackage[utf8]{inputenc}

\\title{Untitled}
\\author{}
\\date{\\today}

\\begin{document}
\\maketitle

Hello LaTeX.

\\end{document}
"""


class CompileSignals(QObject):
    started = Signal(str, int)
    finished = Signal(object)
    external_changed = Signal(str)


@dataclass
class EditorTab:
    editor: LaTeXEditor
    path: Path | None = None
    encoding: str = "utf-8"
    manager: CompileManager | None = None
    modified: bool = False
    dirty: bool = False
    external_conflict: bool = False
    pending_compile_after_save: bool = False
    save_timer: QTimer | None = None


@dataclass(frozen=True)
class EditorViewState:
    cursor_position: int
    horizontal: int
    vertical: int


@dataclass(frozen=True)
class DisplayedPdf:
    root_file: Path
    purpose: BuildPurpose
    revision: int
    path: Path
    build_id: int | None = None


def make_panel(
    title: str,
    body: QWidget,
    hint: str = "",
    actions: list[QWidget] | None = None,
) -> QWidget:
    panel = QWidget()
    panel.setObjectName("panel")

    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    header = QWidget()
    header.setObjectName("panelHeader")
    header.setFixedHeight(36)
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(12, 0, 12, 0)
    header_layout.setSpacing(8)

    title_label = QLabel(title)
    title_label.setObjectName("panelTitle")
    header_layout.addWidget(title_label)

    if hint:
        hint_label = QLabel(hint)
        hint_label.setObjectName("panelHint")
        header_layout.addWidget(hint_label)

    header_layout.addStretch()

    for action in actions or []:
        header_layout.addWidget(action)

    layout.addWidget(header)
    layout.addWidget(body)
    return panel


def set_dynamic_property(widget: QWidget, name: str, value: str) -> None:
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
