from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.gui.icons import icon
from app.gui.main_window_support import set_dynamic_property
from app.gui.theme import COLOR_TEXT_FAINT

try:
    from PySide6.QtPdf import QPdfDocument, QPdfSearchModel
    from PySide6.QtPdfWidgets import QPdfView
except ImportError:  # pragma: no cover - depends on installed PySide6 extras
    QPdfDocument = None  # type: ignore[assignment]
    QPdfSearchModel = None  # type: ignore[assignment]
    QPdfView = None  # type: ignore[assignment]


@dataclass(frozen=True)
class PdfViewState:
    page: int
    horizontal: int
    vertical: int
    zoom_factor: float
    zoom_mode: Any


class PdfPanel(QWidget):
    sourceRequested = Signal(int, float, float)

    _PDF_TOOLBAR_NARROW_WIDTH = 700

    def __init__(self) -> None:
        super().__init__()
        self.current_pdf: Path | None = None
        self.current_logical_key: Path | None = None
        self._document: Any = None
        self._view: Any = None
        self._search_model: Any = None
        self._search_index = -1
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._build_toolbar(layout)
        self.freshness_label = QLabel("尚未编译")
        self.freshness_label.setObjectName("pdfFreshnessBanner")
        self.freshness_label.setProperty("severity", "neutral")
        layout.addWidget(self.freshness_label)

        if QPdfDocument is not None and QPdfView is not None:
            self._document = QPdfDocument(self)
            self._view = QPdfView(self)
            self._view.setDocument(self._document)
            self._view.setPageMode(QPdfView.PageMode.MultiPage)
            self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
            self._view.viewport().installEventFilter(self)
            self._view.viewport().setToolTip("双击 PDF 定位源码；快速预览与正式 PDF 均需为当前版本。")
            self.page_spin.valueChanged.connect(self.jump_to_page)
            self.prev_page_button.clicked.connect(lambda: self.jump_to_page(self.current_page() - 1))
            self.next_page_button.clicked.connect(lambda: self.jump_to_page(self.current_page() + 1))
            self.zoom_in_button.clicked.connect(lambda: self.zoom_by(1.15))
            self.zoom_out_button.clicked.connect(lambda: self.zoom_by(1 / 1.15))
            self.fit_width_button.clicked.connect(self.fit_width)
            self.fit_page_button.clicked.connect(self.fit_page)
            self._view.pageNavigator().currentPageChanged.connect(lambda _page: self._update_page_controls())
            if QPdfSearchModel is not None:
                self._search_model = QPdfSearchModel(self)
                self._search_model.setDocument(self._document)
                self._view.setSearchModel(self._search_model)
                self._search_model.countChanged.connect(self._on_pdf_search_count_changed)
                self.pdf_search_edit.textChanged.connect(self._search_pdf)
                self.pdf_search_edit.returnPressed.connect(lambda: self.goto_pdf_search_result(1))
                self.pdf_search_prev_button.clicked.connect(lambda: self.goto_pdf_search_result(-1))
                self.pdf_search_next_button.clicked.connect(lambda: self.goto_pdf_search_result(1))
            else:
                self._set_pdf_search_enabled(False)
            self._stack = QStackedWidget()
            self._stack.setObjectName("pdfStack")
            self._empty_state = self._build_empty_state()
            self._stack.addWidget(self._empty_state)
            self._stack.addWidget(self._view)
            self._stack.setCurrentWidget(self._empty_state)
            layout.addWidget(self._stack)
            self._set_pdf_toolbar_enabled(False)
        else:
            self._set_pdf_toolbar_enabled(False)
            label = QLabel("PDF 预览需要 PySide6 QtPdf 支持。")
            label.setObjectName("panelHint")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)

    def _build_toolbar(self, layout: QVBoxLayout) -> None:
        toolbar = QWidget()
        toolbar.setObjectName("pdfToolbar")
        self._toolbar = toolbar
        toolbar.installEventFilter(self)
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(6)
        self.prev_page_button = self._icon_button("chevron-left", "上一页")
        self.next_page_button = self._icon_button("chevron-right", "下一页")
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 1)
        self.page_spin.setMinimumWidth(64)
        self.page_spin.setAccessibleName("PDF 页码")
        self.page_count_label = QLabel("/ 0")
        self.zoom_out_button = self._icon_button("zoom-out", "缩小")
        self.zoom_in_button = self._icon_button("zoom-in", "放大")
        self.fit_width_button = self._icon_button("move-horizontal", "适合宽度")
        self.fit_page_button = self._icon_button("maximize", "适合页面")
        self.pdf_search_edit = QLineEdit()
        self.pdf_search_edit.setPlaceholderText("搜索 PDF")
        self.pdf_search_edit.setAccessibleName("搜索 PDF")
        self.pdf_search_prev_button = self._icon_button("chevron-left", "上一个匹配")
        self.pdf_search_next_button = self._icon_button("chevron-right", "下一个匹配")
        self.pdf_search_status = QLabel("")
        self.export_pdf_button = self._icon_button("save", "导出 PDF")
        reveal_tooltip = "在 Finder 中显示" if sys.platform == "darwin" else "在文件夹中显示"
        self.reveal_pdf_button = self._icon_button("folder-open", reveal_tooltip)
        self.export_pdf_button.setEnabled(False)
        self.reveal_pdf_button.setEnabled(False)
        core_widgets = (
            self.page_spin,
            self.page_count_label,
            self.zoom_out_button,
            self.zoom_in_button,
            self.fit_width_button,
        )
        secondary_widgets = (
            self.prev_page_button,
            self.next_page_button,
            self.fit_page_button,
            self.pdf_search_edit,
            self.pdf_search_prev_button,
            self.pdf_search_next_button,
            self.pdf_search_status,
            self.export_pdf_button,
            self.reveal_pdf_button,
        )
        for widget in core_widgets:
            row.addWidget(widget)
        row.addStretch()
        self._secondary_panel = QWidget()
        secondary_row = QHBoxLayout(self._secondary_panel)
        secondary_row.setContentsMargins(0, 0, 0, 0)
        secondary_row.setSpacing(6)
        for widget in secondary_widgets:
            secondary_row.addWidget(widget)
        row.addWidget(self._secondary_panel)
        self._more_button = QToolButton()
        self._more_button.setText("更多")
        self._more_button.setObjectName("pdfMoreButton")
        self._more_button.setMenu(self._build_overflow_menu())
        self._more_button.hide()
        row.addWidget(self._more_button)
        layout.addWidget(toolbar)
        self._update_toolbar_mode()

    def _build_overflow_menu(self) -> QMenu:
        menu = QMenu(self)
        reveal_label = "在 Finder 中显示" if sys.platform == "darwin" else "在文件夹中显示"
        entries = (
            ("上一页", self.prev_page_button),
            ("下一页", self.next_page_button),
            ("适合页面", self.fit_page_button),
            ("导出 PDF", self.export_pdf_button),
            (reveal_label, self.reveal_pdf_button),
        )
        for label, button in entries:
            action = QAction(label, menu)
            action.triggered.connect(button.clicked.emit)
            menu.addAction(action)
        return menu

    def _update_toolbar_mode(self) -> None:
        if not hasattr(self, "_toolbar"):
            return
        narrow = self._toolbar.width() < self._PDF_TOOLBAR_NARROW_WIDTH
        self._secondary_panel.setVisible(not narrow)
        self._more_button.setVisible(narrow)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_toolbar_mode()

    @staticmethod
    def _icon_button(icon_name: str, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName("iconButton")
        button.setIcon(icon(icon_name, size=16))
        button.setIconSize(QSize(16, 16))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        return button

    @staticmethod
    def _build_empty_state() -> QWidget:
        state = QWidget()
        state.setObjectName("pdfEmptyState")
        layout = QVBoxLayout(state)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)
        mark = QLabel()
        mark.setObjectName("pdfEmptyIcon")
        mark.setPixmap(icon("files", COLOR_TEXT_FAINT, 36).pixmap(36, 36))
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("PDF 预览")
        title.setObjectName("pdfEmptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("编译成功后，文档将显示在这里。")
        hint.setObjectName("panelHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mark)
        layout.addWidget(title)
        layout.addWidget(hint)
        return state

    def load_pdf(self, path: Path, *, logical_key: Path | None = None) -> None:
        # Restore page/scroll/zoom only when reloading the same document;
        # preview and final PDFs for the same root share one logical document.
        document_key = logical_key if logical_key is not None else path
        same_document = self.current_logical_key == document_key
        self.current_pdf = path
        self.current_logical_key = document_key
        if self._document is not None and path.exists():
            self._set_pdf_toolbar_enabled(True)
            state = self._capture_state() if same_document else None
            self._document.close()
            self._document.load(str(path))
            self._search_index = -1
            if self._search_model is not None:
                self._search_model.setSearchString(self.pdf_search_edit.text())
            if hasattr(self, "_stack"):
                self._stack.setCurrentWidget(self._view)
            self._restore_state_later(state)
            QTimer.singleShot(0, self._update_page_controls)
            QTimer.singleShot(120, self._update_page_controls)

    def clear_pdf(self) -> None:
        self.current_pdf = None
        self.current_logical_key = None
        self._search_index = -1
        self._set_pdf_toolbar_enabled(False)
        if self._document is not None:
            self._document.close()
        if self._search_model is not None:
            self._search_model.setSearchString("")
        self.pdf_search_edit.clear()
        self._update_pdf_search_status()
        if hasattr(self, "_stack"):
            self._stack.setCurrentWidget(self._empty_state)
        if self._document is not None:
            self._update_page_controls()

    def set_freshness(self, text: str, severity: str) -> None:
        self.freshness_label.setText(text)
        set_dynamic_property(self.freshness_label, "severity", severity)

    def eventFilter(self, watched: QObject, event: Any) -> bool:
        if watched is getattr(self, "_toolbar", None) and event.type() == QEvent.Type.Resize:
            self._update_toolbar_mode()
            return False
        if (
            self._view is not None
            and watched == self._view.viewport()
            and event.type() == QEvent.Type.MouseButtonDblClick
            and event.button() == Qt.MouseButton.LeftButton
        ):
            mapped = self.pdf_position_for_viewport_point(event.position())
            if mapped is not None:
                self.sourceRequested.emit(*mapped)
            return True
        return super().eventFilter(watched, event)

    def jump_to_pdf_position(self, page: int, x: float, y: float) -> None:
        if self._view is None or self._document is None or self._document.pageCount() == 0:
            return
        page_index = max(0, min(page - 1, self._document.pageCount() - 1))
        geometry = self._page_geometry(page_index)
        if geometry is None:
            return
        left, top, _width, _height, zoom = geometry
        viewport = self._view.viewport()
        self._view.verticalScrollBar().setValue(int(top + y * zoom - viewport.height() / 3))
        self._view.horizontalScrollBar().setValue(int(left + x * zoom - viewport.width() / 2))

    def current_page(self) -> int:
        if self._view is None:
            return 1
        return self._view.pageNavigator().currentPage() + 1

    def jump_to_page(self, page: int) -> None:
        if self._view is None or self._document is None or self._document.pageCount() == 0:
            return
        page_index = max(0, min(page - 1, self._document.pageCount() - 1))
        try:
            self._view.pageNavigator().jump(page_index, QPointF(0, 0), self._view.zoomFactor())
        except TypeError:
            page_height = float(self._document.pagePointSize(page_index).height()) * self._effective_zoom(page_index)
            self._view.verticalScrollBar().setValue(int(page_index * page_height))
        self._update_page_controls()

    def zoom_by(self, factor: float) -> None:
        if self._view is None:
            return
        self._view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._view.setZoomFactor(max(0.2, min(5.0, float(self._view.zoomFactor()) * factor)))

    def fit_width(self) -> None:
        if self._view is not None:
            self._view.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def fit_page(self) -> None:
        if self._view is not None:
            self._view.setZoomMode(QPdfView.ZoomMode.FitInView)

    def _search_pdf(self, text: str) -> None:
        self._search_index = -1
        if self._search_model is None:
            return
        if self._view is not None:
            try:
                self._view.setCurrentSearchResultIndex(-1)
            except (TypeError, RuntimeError):
                pass
        self._search_model.setSearchString(text)
        if text:
            self.pdf_search_status.setText("搜索中...")
        self._update_pdf_search_status()

    def goto_pdf_search_result(self, direction: int) -> None:
        if self._search_model is None or self._search_model.count() == 0:
            self._update_pdf_search_status()
            return
        count = self._search_model.count()
        if self._search_index >= 0:
            target = (self._search_index + direction) % count
        else:
            target = 0 if direction >= 0 else count - 1
        self._activate_pdf_search_result(target)
        self._update_pdf_search_status()

    def _on_pdf_search_count_changed(self, *_args: Any) -> None:
        count = self._search_model.count() if self._search_model is not None else 0
        if not self.pdf_search_edit.text() or count == 0:
            self._search_index = -1
            self._update_pdf_search_status()
            return
        if self._search_index < 0:
            QTimer.singleShot(0, lambda: self._activate_pdf_search_result(0))
        else:
            self._update_pdf_search_status()

    def _activate_pdf_search_result(self, index: int) -> None:
        if self._search_model is None or self._search_model.count() == 0:
            return
        count = self._search_model.count()
        self._search_index = max(0, min(index, count - 1))
        if self._view is not None:
            try:
                self._view.setCurrentSearchResultIndex(self._search_index)
            except (TypeError, RuntimeError):
                pass

        page, location = self._pdf_search_result_position(self._search_index)
        if page is None:
            return
        if location is not None:
            self.jump_to_pdf_position(page + 1, float(location.x()), float(location.y()))
            QTimer.singleShot(80, lambda: self.jump_to_pdf_position(page + 1, float(location.x()), float(location.y())))
        else:
            self.jump_to_page(page + 1)
        self._update_pdf_search_status()

    def _pdf_search_result_position(self, index: int) -> tuple[int | None, QPointF | None]:
        if self._search_model is None:
            return None, None
        try:
            link = self._search_model.resultAtIndex(index)
        except (TypeError, RuntimeError):
            link = None
        if link is not None and link.isValid():
            return int(link.page()), link.location()

        model_index = self._search_model.index(index, 0)
        page_role = QPdfSearchModel.Role.Page.value
        location_role = QPdfSearchModel.Role.Location.value
        page = self._search_model.data(model_index, page_role)
        location = self._search_model.data(model_index, location_role)
        return (int(page) if page is not None else None), location if isinstance(location, QPointF) else None

    def _update_pdf_search_status(self) -> None:
        if self._search_model is None:
            self.pdf_search_status.setText("")
            self.pdf_search_prev_button.setEnabled(False)
            self.pdf_search_next_button.setEnabled(False)
            return
        count = self._search_model.count()
        available = self.pdf_search_edit.isEnabled()
        has_matches = available and bool(self.pdf_search_edit.text()) and count > 0
        self.pdf_search_prev_button.setEnabled(has_matches)
        self.pdf_search_next_button.setEnabled(has_matches)
        if not available or not self.pdf_search_edit.text():
            self.pdf_search_status.setText("")
        elif count == 0:
            self.pdf_search_status.setText("无匹配")
        else:
            shown = self._search_index + 1 if self._search_index >= 0 else 0
            self.pdf_search_status.setText(f"{shown}/{count}")

    def _update_page_controls(self) -> None:
        count = self._document.pageCount() if self._document is not None else 0
        current = max(1, self.current_page())
        self.page_spin.blockSignals(True)
        self.page_spin.setRange(1, max(1, count))
        self.page_spin.setValue(current)
        self.page_spin.blockSignals(False)
        self.page_count_label.setText(f"/ {count}")
        has_pages = count > 0
        self.page_spin.setEnabled(has_pages)
        self.prev_page_button.setEnabled(has_pages and current > 1)
        self.next_page_button.setEnabled(has_pages and current < count)
        for widget in (
            self.zoom_out_button,
            self.zoom_in_button,
            self.fit_width_button,
            self.fit_page_button,
        ):
            widget.setEnabled(has_pages)
        self._set_pdf_search_enabled(has_pages)

    def _set_pdf_toolbar_enabled(self, enabled: bool) -> None:
        for widget in (
            self.prev_page_button,
            self.next_page_button,
            self.page_spin,
            self.zoom_out_button,
            self.zoom_in_button,
            self.fit_width_button,
            self.fit_page_button,
        ):
            widget.setEnabled(enabled)
        self._set_pdf_search_enabled(enabled)

    def _set_pdf_search_enabled(self, enabled: bool) -> None:
        self.pdf_search_edit.setEnabled(enabled)
        if not enabled:
            self.pdf_search_prev_button.setEnabled(False)
            self.pdf_search_next_button.setEnabled(False)
            self.pdf_search_status.setText("")
        else:
            self._update_pdf_search_status()

    def pdf_position_for_viewport_point(self, point: Any) -> tuple[int, float, float] | None:
        if self._view is None or self._document is None or self._document.pageCount() == 0:
            return None

        content_x = float(point.x()) + self._view.horizontalScrollBar().value()
        content_y = float(point.y()) + self._view.verticalScrollBar().value()

        for page_index in range(self._document.pageCount()):
            geometry = self._page_geometry(page_index)
            if geometry is None:
                continue
            left, top, width, height, zoom = geometry
            if left <= content_x <= left + width and top <= content_y <= top + height:
                page_size = self._document.pagePointSize(page_index)
                x = _clamp((content_x - left) / zoom, 0.0, float(page_size.width()))
                y = _clamp((content_y - top) / zoom, 0.0, float(page_size.height()))
                return page_index + 1, x, y
        return None

    def _capture_state(self) -> PdfViewState | None:
        if self._view is None:
            return None
        return PdfViewState(
            page=self._view.pageNavigator().currentPage(),
            horizontal=self._view.horizontalScrollBar().value(),
            vertical=self._view.verticalScrollBar().value(),
            zoom_factor=float(self._view.zoomFactor()),
            zoom_mode=self._view.zoomMode(),
        )

    def _restore_state_later(self, state: PdfViewState | None) -> None:
        if state is None:
            return
        QTimer.singleShot(0, lambda: self._restore_state(state))
        QTimer.singleShot(120, lambda: self._restore_state(state))

    def _restore_state(self, state: PdfViewState) -> None:
        if self._view is None:
            return
        self._view.setZoomMode(state.zoom_mode)
        if state.zoom_mode == QPdfView.ZoomMode.Custom:
            self._view.setZoomFactor(state.zoom_factor)
        self._view.horizontalScrollBar().setValue(state.horizontal)
        self._view.verticalScrollBar().setValue(state.vertical)

    def _page_geometry(self, page_index: int) -> tuple[float, float, float, float, float] | None:
        if self._view is None or self._document is None:
            return None
        zoom = self._effective_zoom(page_index)
        margins = self._view.documentMargins()
        spacing = float(self._view.pageSpacing())
        top = float(margins.top())
        for index in range(page_index):
            page_size = self._document.pagePointSize(index)
            top += float(page_size.height()) * zoom + spacing

        page_size = self._document.pagePointSize(page_index)
        width = float(page_size.width()) * zoom
        height = float(page_size.height()) * zoom
        available_width = max(0.0, float(self._view.viewport().width() - margins.left() - margins.right()))
        left = float(margins.left()) + max(0.0, (available_width - width) / 2)
        return left, top, width, height, zoom

    def _effective_zoom(self, page_index: int) -> float:
        if self._view is None or self._document is None:
            return 1.0
        raw_zoom = max(float(self._view.zoomFactor()), 0.01)
        mode = self._view.zoomMode()
        if mode == QPdfView.ZoomMode.Custom:
            return raw_zoom

        margins = self._view.documentMargins()
        page_size = self._document.pagePointSize(page_index)
        available_width = max(1.0, float(self._view.viewport().width() - margins.left() - margins.right()))
        fit_width_zoom = available_width / max(1.0, float(page_size.width()))
        if mode == QPdfView.ZoomMode.FitToWidth:
            return fit_width_zoom

        available_height = max(1.0, float(self._view.viewport().height() - margins.top() - margins.bottom()))
        fit_height_zoom = available_height / max(1.0, float(page_size.height()))
        if mode == QPdfView.ZoomMode.FitInView:
            return min(fit_width_zoom, fit_height_zoom)

        return raw_zoom


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
