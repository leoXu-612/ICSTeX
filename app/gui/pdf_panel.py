from __future__ import annotations

import sys
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPointF, QSize, Qt, QTimer, Signal, Slot
from shiboken6 import isValid
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QApplication,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.gui.icons import icon
from app.core.pdf_identity import PdfContentIdentity
from app.gui.main_window_support import set_dynamic_property
from app.gui.theme import COLOR_TEXT_FAINT, PRIMARY_BUTTON_STATE_STYLE

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
    revealRequested = Signal(object)
    viewChanged = Signal(object)
    availabilityChanged = Signal(bool)
    compileRequested = Signal()

    _PDF_TOOLBAR_NARROW_WIDTH = 700

    def __init__(self, *, search_action: QAction | None = None) -> None:
        super().__init__()
        self.current_pdf: Path | None = None
        self.current_logical_key: Path | None = None
        self._document: Any = None
        self._view: Any = None
        self._view_has_loaded_document = False
        self._has_pages = False
        self._search_model: Any = None
        self._search_index = -1
        self._load_generation = 0
        self._search_generation = 0
        self._loaded_identity = None
        self.last_load_reused = False
        self._search_preedit = False
        self._search_auto_select = False
        self._search_previous_focus = None
        self.search_action = search_action or QAction("搜索 PDF", self)
        self.search_action.setShortcut(QKeySequence("Ctrl+Alt+F"))
        self.search_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.search_action.triggered.connect(self.show_pdf_search)
        self.addAction(self.search_action)
        self._zoom_anchor: tuple[int, float, float] | None = None
        self._zoom_anchor_timer = QTimer(self)
        self._zoom_anchor_timer.setSingleShot(True)
        self._zoom_anchor_timer.timeout.connect(self._finish_zoom)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._build_toolbar(layout)
        self.freshness_label = QLabel("尚未编译")
        self.freshness_label.setObjectName("pdfFreshnessBanner")
        self.freshness_label.setProperty("severity", "neutral")
        layout.addWidget(self.freshness_label)
        self.freshness_label.hide()
        self.display_status = QLabel()
        self.display_status.setObjectName("pdfDisplayStatus")
        self.display_status.setWordWrap(True)
        self.display_status.hide()
        layout.addWidget(self.display_status)

        if QPdfDocument is not None and QPdfView is not None:
            self._document = QPdfDocument()
            # QPdfView captures the primary screen's logical pixels per point.
            self._pdf_screen_resolution = QGuiApplication.primaryScreen().logicalDotsPerInch() / 72.0
            self._view = self._create_pdf_view()
            self.page_spin.valueChanged.connect(self.jump_to_page)
            self.prev_page_button.clicked.connect(lambda: self.jump_to_page(self.current_page() - 1))
            self.next_page_button.clicked.connect(lambda: self.jump_to_page(self.current_page() + 1))
            self.zoom_in_button.clicked.connect(lambda: self.zoom_by(1.15))
            self.zoom_out_button.clicked.connect(lambda: self.zoom_by(1 / 1.15))
            self.fit_width_button.clicked.connect(self.fit_width)
            self.fit_page_button.clicked.connect(self.fit_page)
            if QPdfSearchModel is not None:
                self._search_model = QPdfSearchModel(self)
                self._search_model.setDocument(self._document)
                self._view.setSearchModel(self._search_model)
                self._search_model.countChanged.connect(self._on_pdf_search_count_changed)
                self.pdf_search_edit.textChanged.connect(self._search_pdf)
                self.pdf_search_edit.returnPressed.connect(self._search_enter)
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
            # QObject deletes children in creation/reparenting order. Keep the
            # document after the search model and view stack: render workers
            # must stop before it is freed. Do not parent it to QPdfView, whose
            # private state is destroyed before its child destructors run.
            self._document.setParent(self)
            self._set_pdf_toolbar_enabled(False)
        else:
            self._set_pdf_toolbar_enabled(False)
            label = QLabel("PDF 预览需要 PySide6 QtPdf 支持。")
            label.setObjectName("panelHint")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)

    def _create_pdf_view(self):
        view = QPdfView(self)
        view.setDocument(self._document)
        view.setPageMode(QPdfView.PageMode.MultiPage)
        view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        view.viewport().installEventFilter(self)
        view.viewport().setToolTip("双击 PDF 定位源码；快速预览与正式 PDF 均需为当前版本。")
        view.pageNavigator().currentPageChanged.connect(self._on_page_changed)
        return view

    def _reset_pdf_view(self) -> bool:
        # Qt 6.11's renderer retains requests dropped while its document is
        # closed, and its page cache accepts late results without a document
        # generation. A new view gives changed PDF bytes a fresh render queue.
        # The panel, toolbar, document and search model remain stable.
        old = self._view
        focused = old.hasFocus()
        old.pageNavigator().currentPageChanged.disconnect(self._on_page_changed)
        old.viewport().removeEventFilter(self)
        old.setSearchModel(None)
        old.setDocument(None)  # Synchronizes with any active native render.
        self._view = self._create_pdf_view()
        self._view.setSearchModel(self._search_model)
        self._stack.addWidget(self._view)
        self._stack.removeWidget(old)
        old.hide()
        old.deleteLater()
        if self._search_previous_focus and self._search_previous_focus() is old:
            self._search_previous_focus = weakref.ref(self._view)
        self.viewChanged.emit(self._view)
        return focused

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
        self.page_count_label = QLabel("")
        self.toolbar_title = QLabel("PDF")
        self.zoom_out_button = self._icon_button("zoom-out", "缩小")
        self.zoom_in_button = self._icon_button("zoom-in", "放大")
        self.fit_width_button = self._icon_button("move-horizontal", "适合宽度")
        self.fit_page_button = self._icon_button("maximize", "适合页面")
        self.pdf_search_edit = QLineEdit()
        self.pdf_search_edit.setPlaceholderText("搜索 PDF")
        self.pdf_search_edit.setAccessibleName("搜索 PDF")
        self.pdf_search_edit.installEventFilter(self)
        search_keys = self.search_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        self.pdf_search_button = self._icon_button("search", f"搜索 PDF（{search_keys}）")
        self.pdf_search_button.clicked.connect(self.search_action.trigger)
        self.pdf_search_prev_button = self._icon_button("chevron-left", "上一个匹配")
        self.pdf_search_next_button = self._icon_button("chevron-right", "下一个匹配")
        self.pdf_search_status = QLabel("")
        self.pdf_search_status.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self.export_pdf_button = self._icon_button("save", "导出 PDF")
        reveal_tooltip = "在 Finder 中显示" if sys.platform == "darwin" else "在文件夹中显示"
        self.reveal_pdf_button = self._icon_button("folder-open", reveal_tooltip)
        self.export_pdf_button.setEnabled(False)
        self.reveal_pdf_button.setEnabled(False)
        core_widgets = (
            self.toolbar_title,
            self.page_spin,
            self.page_count_label,
            self.zoom_out_button,
            self.zoom_in_button,
            self.fit_width_button,
            self.pdf_search_button,
        )
        secondary_widgets = (
            self.prev_page_button,
            self.next_page_button,
            self.fit_page_button,
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
        self._more_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._more_button.setMenu(self._build_overflow_menu())
        self._more_button.hide()
        row.addWidget(self._more_button)
        layout.addWidget(toolbar)
        toolbar.hide()
        self._search_row = QWidget()
        self._search_row.setObjectName("pdfSearchToolbar")
        search_layout = QHBoxLayout(self._search_row)
        search_layout.setContentsMargins(8, 2, 8, 4)
        search_layout.setSpacing(6)
        search_layout.addWidget(self.pdf_search_edit, 1)
        search_layout.addWidget(self.pdf_search_prev_button)
        search_layout.addWidget(self.pdf_search_next_button)
        search_layout.addWidget(self.pdf_search_status)
        self.pdf_search_close_button = self._icon_button("chevron-up", "关闭 PDF 搜索（Esc）")
        self.pdf_search_close_button.clicked.connect(self.hide_pdf_search)
        search_layout.addWidget(self.pdf_search_close_button)
        layout.addWidget(self._search_row)
        self._search_row.hide()
        self._update_toolbar_mode()

    def _build_overflow_menu(self) -> QMenu:
        menu = QMenu(self)
        self._overflow_actions = {}
        reveal_label = "在 Finder 中显示" if sys.platform == "darwin" else "在文件夹中显示"
        entries = (
            ("搜索 PDF", self.pdf_search_button),
            ("上一页", self.prev_page_button),
            ("下一页", self.next_page_button),
            ("适合页面", self.fit_page_button),
            ("导出 PDF", self.export_pdf_button),
            (reveal_label, self.reveal_pdf_button),
        )
        for label, button in entries:
            action = QAction(label, menu)
            action.setEnabled(button.isEnabled())
            action.triggered.connect(button.click)
            self._overflow_actions[button] = action
            button.installEventFilter(self)
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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # The same action is used in menus and as the window shortcut, also
        # for a PdfPanel hosted outside MainWindow. No duplicate shortcut.
        self.window().addAction(self.search_action)

    def show_pdf_search(self) -> None:
        if not self.pdf_search_edit.isEnabled():
            return
        focus = QApplication.focusWidget()
        if focus is not None and focus.window() is self.window() and not self._search_row.isAncestorOf(focus):
            self._search_previous_focus = weakref.ref(focus)
        self.revealRequested.emit(self)
        self._search_row.show()
        self.pdf_search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        if not self._search_preedit:
            self.pdf_search_edit.selectAll()

    def hide_pdf_search(self) -> None:
        if self._search_preedit:
            return
        self._search_generation += 1
        self._search_row.hide()
        previous = self._search_previous_focus() if self._search_previous_focus else None
        if previous is not None and isValid(previous):
            self.revealRequested.emit(previous)
        if previous is not None and isValid(previous) and previous.isVisible() and previous.isEnabled():
            previous.setFocus(Qt.FocusReason.ShortcutFocusReason)
        elif self._view is not None:
            self._view.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _search_enter(self):
        if not self._search_preedit:
            self.goto_pdf_search_result(1)

    @staticmethod
    def _icon_button(icon_name: str, tooltip: str) -> QPushButton:
        button = QPushButton()
        button.setObjectName("iconButton")
        button.setIcon(icon(icon_name, size=16))
        button.setIconSize(QSize(16, 16))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        return button

    def _build_empty_state(self) -> QWidget:
        state = QWidget()
        state.setObjectName("pdfEmptyState")
        layout = QVBoxLayout(state)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)
        mark = QLabel()
        mark.setObjectName("pdfEmptyIcon")
        mark.setPixmap(icon("files", COLOR_TEXT_FAINT, 36).pixmap(36, 36))
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("还没有 PDF 预览")
        title.setObjectName("pdfEmptyTitle")
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("先编译一次，即可在这里查看排版结果。")
        hint.setObjectName("pdfEmptyHint")
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint = hint
        self.empty_compile_button = QPushButton("编译并显示 PDF")
        self.empty_compile_button.setObjectName("primaryButton")
        self.empty_compile_button.setStyleSheet(PRIMARY_BUTTON_STATE_STYLE)
        self.empty_compile_button.clicked.connect(lambda: self.compileRequested.emit())
        layout.addWidget(mark)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(8)
        layout.addWidget(self.empty_compile_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.setContentsMargins(20, 20, 20, 20)
        return state

    def load_pdf(self, path: Path, *, logical_key: Path | None = None,
                 content_identity: PdfContentIdentity | None = None) -> None:
        # Restore page/scroll/zoom only when reloading the same document;
        # preview and final PDFs for the same root share one logical document.
        document_key = logical_key if logical_key is not None else path
        same_document = self.current_logical_key == document_key
        self.last_load_reused = bool(
            same_document and self.current_pdf == path and content_identity is not None
            and self._loaded_identity is not None
            and content_identity.digest == self._loaded_identity.digest
            and content_identity.still_matches(path) and self._document is not None
            and self._document.status() == QPdfDocument.Status.Ready)
        if self.last_load_reused:
            self._loaded_identity = content_identity
            self.display_status.setText("PDF 内容未变化，保留当前阅读位置")
            self.display_status.hide()
            return
        self._load_generation += 1
        self._loaded_identity = None
        self._cancel_pending_zoom()
        self.current_pdf = path
        self.current_logical_key = document_key
        self.display_status.setText("正在载入 PDF 文件…")
        self.display_status.show()
        if self._document is not None and path.exists():
            self._set_pdf_toolbar_enabled(True)
            state = self._capture_state() if same_document else None
            focused = self._reset_pdf_view() if self._view_has_loaded_document else False
            self._view_has_loaded_document = True
            self._document.close()
            error = self._document.load(str(path))
            if (error == QPdfDocument.Error.None_ and content_identity is not None
                    and content_identity.still_matches(path)):
                self._loaded_identity = content_identity
            self.display_status.setText("PDF 文件已载入；页面由查看器绘制" if error == QPdfDocument.Error.None_
                                        else "PDF 文件载入失败；编译结果不等于显示成功")
            self.display_status.setVisible(error != QPdfDocument.Error.None_)
            self._search_index = -1
            self._search_auto_select = False
            if self._search_model is not None:
                self._search_model.setSearchString(self.pdf_search_edit.text())
            self._update_page_controls()
            if hasattr(self, "_stack"):
                self._stack.setCurrentWidget(self._view)
            if focused:
                self._view.setFocus(Qt.FocusReason.OtherFocusReason)
            self._restore_state_later(state)
            QTimer.singleShot(0, self, self._update_page_controls)
            QTimer.singleShot(120, self, self._update_page_controls)
        else:
            self.display_status.setText("PDF 文件不可用，尚未载入新内容")

    def clear_pdf(self) -> None:
        self._cancel_pending_zoom()
        self._load_generation += 1
        self._loaded_identity = None
        self.last_load_reused = False
        self.display_status.clear()
        self.display_status.hide()
        self.current_pdf = None
        self.current_logical_key = None
        self._search_index = -1
        self._search_preedit = False
        self._search_auto_select = False
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
        # Compilation freshness is not a successful viewer load. Reuse the
        # existing load-error indication, without render polling or extra work.
        if severity == "success" and not self.display_status.isHidden():
            text = self.display_status.text()
            severity = "warning"
        self.freshness_label.setText(text)
        set_dynamic_property(self.freshness_label, "severity", severity)
        self.freshness_label.setVisible(self._has_pages)
        if not self._has_pages and hasattr(self, "_empty_hint"):
            self._empty_hint.setText("先编译一次，即可在这里查看排版结果。" if text == "尚未编译" else text)

    def eventFilter(self, watched: QObject, event: Any) -> bool:
        if watched is getattr(self, "pdf_search_edit", None):
            if event.type() == QEvent.Type.InputMethod:
                self._search_preedit = bool(event.preeditString())
            elif event.type() == QEvent.Type.ShortcutOverride and event.key() == Qt.Key.Key_Escape:
                event.accept()
                return True
            elif event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                if not self._search_preedit:
                    self.hide_pdf_search()
                return True
            elif (event.type() == QEvent.Type.KeyPress and event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}
                  and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
                                               | Qt.KeyboardModifier.MetaModifier)):
                self._search_enter()
                return True
        if event.type() == QEvent.Type.EnabledChange:
            action = getattr(self, "_overflow_actions", {}).get(watched)
            if action is not None:
                action.setEnabled(watched.isEnabled())
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
        self._cancel_pending_zoom()
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
        self._cancel_pending_zoom()
        if self._view is None or self._document is None or self._document.pageCount() == 0:
            return
        page_index = max(0, min(page - 1, self._document.pageCount() - 1))
        try:
            self._view.pageNavigator().jump(page_index, QPointF(0, 0), self._view.zoomFactor())
        except TypeError:
            pass
        # The navigator can retain its page number after a layout-only change;
        # jumping to that same number emits no currentPageChanged signal.
        geometry = self._page_geometry(page_index)
        if geometry is not None:
            self._view.verticalScrollBar().setValue(round(geometry[1]))
        self._update_page_controls()

    def zoom_by(self, factor: float) -> None:
        if self._view is None or self._document is None or self._document.pageCount() == 0:
            return
        zoom = self._effective_zoom(self.current_page() - 1) / self._pdf_screen_resolution
        self._set_view_zoom(QPdfView.ZoomMode.Custom, max(0.2, min(5.0, zoom * factor)))

    def fit_width(self) -> None:
        if self._view is not None:
            self._set_view_zoom(QPdfView.ZoomMode.FitToWidth)

    def fit_page(self) -> None:
        if self._view is not None:
            self._set_view_zoom(QPdfView.ZoomMode.FitInView)

    def _set_view_zoom(self, mode: Any, factor: float | None = None) -> None:
        self._cancel_pending_zoom()
        page = self.current_page() - 1
        geometry = self._page_geometry(page) if self._document.pageCount() else None
        viewport = self._view.viewport()
        if geometry is not None:
            left, top, width, height, zoom = geometry
            # Qt identifies the current page at 40% of the viewport height.
            x = _clamp(self._view.horizontalScrollBar().value() + viewport.width() / 2 - left, 0, width) / zoom
            y = _clamp(self._view.verticalScrollBar().value() + viewport.height() * .4 - top, 0, height) / zoom
        self._view.setZoomMode(mode)
        if factor is not None:
            self._view.setZoomFactor(factor)
        if geometry is not None:
            self._zoom_anchor = (page, x, y)
            self._apply_zoom_anchor(self._zoom_anchor)
            # A newly shown/hidden scrollbar resizes the viewport next turn.
            self._zoom_anchor_timer.start(0)

    def _cancel_pending_zoom(self) -> None:
        self._zoom_anchor_timer.stop()
        self._zoom_anchor = None

    def _finish_zoom(self) -> None:
        anchor = self._zoom_anchor
        self._zoom_anchor = None
        if anchor is not None:
            self._apply_zoom_anchor(anchor)

    def _apply_zoom_anchor(self, anchor: tuple[int, float, float]) -> None:
        page, x, y = anchor
        left, top, width, height, zoom = self._page_geometry(page)
        viewport = self._view.viewport()
        if self._view.zoomMode() == QPdfView.ZoomMode.FitInView:
            # Fit Page promises the whole page, not the previous reading point.
            horizontal = left + (width - viewport.width()) / 2
            vertical = top + (height - viewport.height()) / 2
        else:
            horizontal = left + x * zoom - viewport.width() / 2
            vertical = top + y * zoom - viewport.height() * .4
        self._view.horizontalScrollBar().setValue(round(horizontal))
        self._view.verticalScrollBar().setValue(round(vertical))
        self._update_page_controls()

    def _search_pdf(self, text: str) -> None:
        self._search_generation += 1
        self._search_auto_select = bool(text)
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
        if self._search_preedit:
            return
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
        if self._search_index < 0 and self._search_auto_select and self._search_row.isVisible():
            self._defer_view(0, lambda: self._activate_pdf_search_result(0), search=True)
        # Reload preserves the viewport instead of auto-selecting a match, but
        # asynchronous search counts must still reach the toolbar.
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
            self._defer_view(80, lambda: self.jump_to_pdf_position(page + 1, float(location.x()), float(location.y())), search=True)
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
        text = self.pdf_search_status.text()
        self.pdf_search_status.setMinimumWidth(self.pdf_search_status.fontMetrics().horizontalAdvance(text) + 4 if text else 0)

    def _update_page_controls(self) -> None:
        if self._document is not None and not isValid(self._document):
            return
        count = self._document.pageCount() if self._document is not None else 0
        current = max(1, self.current_page())
        self.page_spin.blockSignals(True)
        self.page_spin.setRange(1, max(1, count))
        self.page_spin.setValue(current)
        self.page_spin.blockSignals(False)
        self.page_count_label.setText(f"/ {count}" if count else "")
        has_pages = count > 0
        self._toolbar.setVisible(has_pages)
        self.freshness_label.setVisible(has_pages)
        if not has_pages:
            self._search_row.hide()
        if self._has_pages != has_pages:
            self._has_pages = has_pages
            self.availabilityChanged.emit(has_pages)
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

    @Slot(int)
    def _on_page_changed(self, _page):
        if (self._document is not None and isValid(self._document)
                and isValid(self.page_spin) and isValid(self.search_action)):
            self._update_page_controls()

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
        self.search_action.setEnabled(enabled)
        self.pdf_search_button.setEnabled(enabled)
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
        self._defer_view(0, lambda: self._restore_state(state))
        self._defer_view(120, lambda: self._restore_state(state))

    def _defer_view(self, milliseconds, callback, *, search=False):
        generation = self._load_generation
        query = self._search_generation
        QTimer.singleShot(milliseconds, self, lambda: callback() if (
            generation == self._load_generation and (not search or query == self._search_generation)) else None)

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
        margins = self._view.documentMargins()
        pages = [self._page_size_and_scale(index) for index in range(self._document.pageCount())]
        size, zoom = pages[page_index]
        top = margins.top() + sum(item[0].height() + self._view.pageSpacing() for item in pages[:page_index])
        total_width = max(item[0].width() for item in pages) + margins.left() + margins.right()
        left = (max(total_width, self._view.viewport().width()) - size.width()) // 2
        return float(left), float(top), float(size.width()), float(size.height()), zoom

    def _effective_zoom(self, page_index: int) -> float:
        if self._view is None or self._document is None:
            return 1.0
        return self._page_size_and_scale(page_index)[1]

    def _page_size_and_scale(self, page_index: int) -> tuple[QSize, float]:
        # Match QPdfView's integer layout, DPI and per-page fit sizes. Reusing
        # one page's scale for all earlier pages breaks mixed-size documents.
        points = self._document.pagePointSize(page_index)
        resolution = self._pdf_screen_resolution
        raw_zoom = max(float(self._view.zoomFactor()), 0.01)
        mode = self._view.zoomMode()
        if mode == QPdfView.ZoomMode.Custom:
            return (points * (resolution * raw_zoom)).toSize(), resolution * raw_zoom
        size = (points * resolution).toSize()
        margins = self._view.documentMargins()
        width = max(1, self._view.viewport().width() - margins.left() - margins.right())
        if mode == QPdfView.ZoomMode.FitToWidth:
            scale = width / max(1, size.width())
            return size * scale, resolution * scale
        height = max(1, self._view.viewport().height() - self._view.pageSpacing())
        fitted = size.scaled(QSize(width, height), Qt.AspectRatioMode.KeepAspectRatio)
        return fitted, resolution * fitted.width() / max(1, size.width())


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
