"""Instance-stable editor/PDF layout shared by source and Block workspaces."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QSizePolicy, QSplitter,
                               QToolButton, QVBoxLayout, QWidget)


class EditorPdfArea(QWidget):
    def __init__(self, editor, pdf, *, editor_label="编辑 Block", compact_width=720,
                 compact_columns=60, wide_sizes=(3, 2)):
        super().__init__()
        self.editor, self.pdf = editor, pdf
        self._compact = None
        self._show_pdf = False
        self._document_available = True
        self._preview_available = True
        self._wide_sizes = list(wide_sizes)
        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self._restore_wide_sizes)
        self._compact_width = compact_width
        self._compact_columns = compact_columns
        self.switcher = QWidget()
        self.switcher.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(self.switcher)
        row.setContentsMargins(0, 0, 0, 0)
        self.editor_button = QToolButton()
        self.editor_button.setText(editor_label)
        self.pdf_button = QToolButton()
        self.pdf_button.setText("查看 PDF")
        for button in (self.editor_button, self.pdf_button):
            button.setObjectName("workspaceViewButton")
            button.setCheckable(True)
            row.addWidget(button)
        row.addStretch()
        self.editor_button.clicked.connect(lambda: self.select_pdf(False))
        self.pdf_button.clicked.connect(lambda: self.select_pdf(True))
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(editor)
        self.splitter.addWidget(pdf)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.splitterMoved.connect(self._remember_wide_sizes)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.switcher)
        layout.addWidget(self.splitter)
        self._arrange()

    def set_document_available(self, available):
        if self._document_available == available:
            return
        self._document_available = available
        self._arrange()

    def select_pdf(self, selected):
        self._show_pdf = selected
        self._arrange()

    def set_preview_available(self, available):
        if self._preview_available == available:
            return
        self._preview_available = available
        self._arrange()
        if not self._compact and self._document_available:
            self._restore_timer.start(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange) and hasattr(self, "splitter"):
            self._arrange()

    def _is_compact(self):
        return self.width() < max(self._compact_width,
            self.fontMetrics().horizontalAdvance("M") * self._compact_columns)

    def _remember_wide_sizes(self, *_):
        if self._compact is False and self._document_available and self._preview_available and not self.pdf.isHidden():
            # Only a handle move changes the user's preference. Minimum-size
            # clamping during font/window layout must not become a new ratio.
            self._wide_sizes = self.splitter.sizes()

    def _restore_wide_sizes(self):
        if self._compact or not self._document_available or self._is_compact():
            return
        available = max(0, self.splitter.contentsRect().width() - self.splitter.handleWidth())
        first = (round(available * self._wide_sizes[0] / sum(self._wide_sizes)) if self._preview_available
                 else max(0, available - self.pdf.maximumWidth()))
        self.splitter.setSizes([first, available - first])

    def _arrange(self):
        compact = self._is_compact()
        manager = getattr(QApplication.instance(), "ui_scale_manager", None)
        empty_width = round(260 * (manager.scale if manager is not None else 1.0))
        self.pdf.setMaximumWidth(16777215 if compact or self._preview_available else empty_width)
        single = compact or not self._document_available
        was_single = self._compact or self.pdf.isHidden()
        if single and not was_single:
            focus = QApplication.focusWidget()
            if focus is not None and (focus is self.pdf or self.pdf.isAncestorOf(focus)):
                self._show_pdf = True
            elif focus is not None and (focus is self.editor or self.editor.isAncestorOf(focus)):
                self._show_pdf = False
        self._compact = compact
        self.switcher.setVisible(compact and self._document_available)
        self.editor.setVisible(not self._document_available or not compact or not self._show_pdf)
        self.pdf.setVisible(self._document_available and (not compact or self._show_pdf))
        if single:
            self._restore_timer.stop()
        elif was_single and self._wide_sizes and all(self._wide_sizes):
            # Restore once, after the splitter receives its final wide geometry.
            # Reapplying on every internal resize can oscillate PDF scrollbars.
            self._restore_timer.start(0)
        self.editor_button.setChecked(not self._show_pdf)
        self.pdf_button.setChecked(self._show_pdf)
