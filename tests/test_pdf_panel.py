from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QSpinBox
from PySide6.QtCore import QPoint, QPointF, QSizeF, Qt
from PySide6.QtTest import QTest

from app.gui.pdf_panel import PdfPanel, PdfViewState


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def _write_zoom_pdf(path: Path, *, mixed: bool = False, color=Qt.GlobalColor.red) -> None:
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPainter, QPageSize, QPdfWriter
    writer = QPdfWriter(str(path))
    writer.setResolution(72)
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    painter = QPainter(writer)
    for page in range(3):
        if page:
            if mixed:
                writer.setPageSize(QPageSize(QSizeF(800 if page == 1 else 500, 700), QPageSize.Unit.Point))
            writer.newPage()
        painter.drawText(40, 60, f"Synthetic zoom page {page + 1}")
        painter.fillRect(100, 100, 120, 80, color)
    painter.end()
    del writer


class PdfPanelToolbarTests(TestCase):
    def test_successful_compile_does_not_hide_viewer_load_failure(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        panel = PdfPanel()
        try:
            with TemporaryDirectory() as temporary:
                panel.load_pdf(Path(temporary) / "missing.pdf")
                panel.set_freshness("PDF 已是最新", "success")
                self.assertEqual(panel.freshness_label.property("severity"), "warning")
                self.assertIn("尚未载入", panel.freshness_label.text())
        finally:
            panel.close()
            panel.deleteLater()
            app.processEvents()

    def setUp(self) -> None:
        _app()

    def test_pending_render_from_cleared_document_cannot_block_reopened_pdf(self):
        from PySide6.QtCore import QSize
        from PySide6.QtPdf import QPdfPageRenderer
        from tools.bench_auto_compile_latency import marker_pixels
        panel = PdfPanel()
        self.addCleanup(panel.close)
        self.addCleanup(panel.clear_pdf)
        with TemporaryDirectory() as directory:
            first, second = (Path(directory) / name for name in ("first.pdf", "second.pdf"))
            _write_zoom_pdf(first)
            _write_zoom_pdf(second, color=Qt.GlobalColor.blue)
            panel.resize(900, 650)
            panel.show()
            panel.load_pdf(first)
            panel._view.setZoomMode(panel._view.ZoomMode.Custom)
            panel._view.setZoomFactor(1.)
            QTest.qWait(200)
            renderer = panel._view.findChild(QPdfPageRenderer)
            # SingleThreaded preserves the same queued-worker implementation,
            # but lets the test deterministically clear before it handles a job.
            renderer.setRenderMode(QPdfPageRenderer.RenderMode.SingleThreaded)
            geometry = panel._page_geometry(0)
            dpr = panel._view.devicePixelRatioF()
            size = QSize(round(geometry[2] * dpr), round(geometry[3] * dpr))
            request = renderer.requestPage(0, size)
            self.assertGreater(request, 0)
            panel.clear_pdf()
            QTest.qWait(20)  # The queued worker sees a closed document.
            panel.load_pdf(second)
            panel._view.setZoomMode(panel._view.ZoomMode.Custom)
            panel._view.setZoomFactor(1.)
            QTest.qWait(300)
            image = panel._view.viewport().grab().toImage()
            capture = os.environ.get("ICSTEX_PDF_RACE_CAPTURE")
            if capture:
                output = Path(capture)
                output.mkdir(parents=True, exist_ok=False)
                image.save(str(output / "viewport.png"))
                (output / "first.pdf").write_bytes(first.read_bytes())
                (output / "second.pdf").write_bytes(second.read_bytes())
            self.assertGreater(marker_pixels(image, (0, 0, 255)), 100,
                               "Closed-document pending request left the new PDF permanently blank")

    def test_old_view_restore_is_discarded_after_document_clear(self):
        panel = PdfPanel()
        self.addCleanup(panel.close)
        state = PdfViewState(1, 100, 400, 1.5, panel._view.ZoomMode.Custom)
        callbacks = []
        with patch("app.gui.pdf_panel.QTimer.singleShot", side_effect=lambda _ms, _owner, callback: callbacks.append(callback)), \
             patch.object(panel, "_restore_state") as restore:
            panel._restore_state_later(state)
            old = list(callbacks)
            panel.clear_pdf()
            for callback in old:
                callback()
            restore.assert_not_called()

    def test_document_outlives_search_and_native_renderer_on_panel_destruction(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtPdf import QPdfPageRenderer
        panel = PdfPanel()
        events = []
        panel._document.destroyed.connect(lambda: events.append("document"))
        panel._search_model.destroyed.connect(lambda: events.append("search"))
        panel._view.findChild(QPdfPageRenderer).destroyed.connect(lambda: events.append("renderer"))
        panel.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertLess(events.index("renderer"), events.index("document"))
        self.assertLess(events.index("search"), events.index("document"))

    def test_late_old_render_cannot_replace_new_document_pixels(self):
        from PySide6.QtCore import QSize
        from PySide6.QtPdf import QPdfPageRenderer, QPdfDocumentRenderOptions
        from tools.bench_auto_compile_latency import marker_pixels
        panel = PdfPanel()
        self.addCleanup(panel.close)
        self.addCleanup(panel.clear_pdf)
        with TemporaryDirectory() as directory:
            first, second = (Path(directory) / name for name in ("first.pdf", "second.pdf"))
            _write_zoom_pdf(first)
            _write_zoom_pdf(second, color=Qt.GlobalColor.blue)
            panel.resize(900, 650)
            panel.show()
            panel.load_pdf(first)
            QTest.qWait(180)
            renderer = panel._view.findChild(QPdfPageRenderer)
            size = QSize(600, 800)
            old_image = panel._document.render(0, size)
            panel.load_pdf(second)
            # Deliver an old generation's already-completed native result after
            # the new load, as a queued worker completion can do in production.
            renderer.pageRendered.emit(0, size, old_image, QPdfDocumentRenderOptions(), 1)
            QTest.qWait(300)
            image = panel._view.viewport().grab().toImage()
            self.assertGreater(marker_pixels(image, (0, 0, 255)), 100)
            self.assertEqual(marker_pixels(image, (255, 0, 0)), 0)

    def test_page_signal_after_document_destruction_does_not_update_controls(self):
        from PySide6.QtCore import QCoreApplication, QEvent
        panel = PdfPanel()
        self.addCleanup(panel.close)
        document = panel._document
        try:
            with patch.object(panel, "_update_page_controls") as update:
                # This test deliberately destroys only the document, not its
                # owner panel. Detach Qt consumers first: otherwise the search
                # timer retains the deliberately freed native document and
                # crashes in an unrelated later test's event loop.
                panel._view.setDocument(None)
                if panel._search_model is not None:
                    panel._search_model.setDocument(None)
                document.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                update.reset_mock()
                panel._view.pageNavigator().currentPageChanged.emit(0)
                update.assert_not_called()
                QTest.qWait(180)
                update.assert_not_called()
        finally:
            panel._document = None

    def test_narrow_pdf_search_has_an_action_and_focusable_field(self):
        panel = PdfPanel()
        self.addCleanup(panel.close)
        self.addCleanup(panel.clear_pdf)
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "search.pdf"
            _write_zoom_pdf(pdf)
            panel.resize(600, 500)
            panel.show()
            panel.load_pdf(pdf)
            QTest.qWait(160)
            actions = {action.text(): action for action in panel._more_button.menu().actions()}
            self.assertIn("搜索 PDF", actions)
            actions["搜索 PDF"].trigger()
            self.assertTrue(panel.pdf_search_edit.isVisible())
            self.assertTrue(panel.pdf_search_edit.hasFocus())
            self.assertFalse(panel.pdf_search_close_button.icon().isNull())

    def test_reload_search_count_updates_without_jumping_to_first_match(self):
        panel = PdfPanel()
        self.addCleanup(panel.close)
        self.addCleanup(panel.clear_pdf)
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "search.pdf"
            _write_zoom_pdf(pdf)
            panel.load_pdf(pdf)
            panel.pdf_search_edit.setText("Synthetic")
            panel._search_auto_select = False
            with patch.object(panel, "_activate_pdf_search_result") as jump:
                for _ in range(100):
                    if panel._search_model.count() == 3:
                        break
                    QTest.qWait(10)
                self.assertEqual(panel._search_model.count(), 3)
                self.assertEqual(panel.pdf_search_status.text(), "0/3")
                jump.assert_not_called()

    def test_verified_same_content_keeps_document_search_and_view_state(self):
        from app.core.pdf_identity import capture_pdf_identity
        panel = PdfPanel()
        self.addCleanup(panel.close)
        self.addCleanup(panel.clear_pdf)
        with TemporaryDirectory() as directory:
            scope = Path(directory).resolve()
            pdf, root = scope / "main.pdf", scope / "main.tex"
            _write_zoom_pdf(pdf)
            panel.resize(600, 500)
            panel.show()
            panel.load_pdf(pdf, logical_key=root, content_identity=capture_pdf_identity(pdf, scope))
            QTest.qWait(160)
            panel.show_pdf_search()
            panel.pdf_search_edit.setText("Synthetic")
            QTest.qWait(160)
            panel.jump_to_page(2)
            QTest.qWait(20)
            before = panel._capture_state()
            selected = panel._search_index
            view = panel._view
            with patch.object(panel._document, "load", wraps=panel._document.load) as load, \
                 patch.object(panel._document, "close", wraps=panel._document.close) as close:
                panel.load_pdf(pdf, logical_key=root, content_identity=capture_pdf_identity(pdf, scope))
                self.assertTrue(panel.last_load_reused)
                load.assert_not_called()
                close.assert_not_called()
            self.assertIs(panel._view, view)
            self.assertEqual(panel._capture_state(), before)
            self.assertEqual(panel._search_index, selected)
            self.assertEqual(panel.pdf_search_edit.text(), "Synthetic")
            self.assertTrue(panel.pdf_search_edit.hasFocus())

    def test_missing_stale_or_different_document_identity_requires_load(self):
        from app.core.pdf_identity import capture_pdf_identity
        panel = PdfPanel()
        self.addCleanup(panel.close)
        self.addCleanup(panel.clear_pdf)
        with TemporaryDirectory() as directory:
            scope = Path(directory).resolve()
            pdf = scope / "main.pdf"
            _write_zoom_pdf(pdf)
            identity = capture_pdf_identity(pdf, scope)
            panel.load_pdf(pdf, logical_key=scope / "main.tex", content_identity=identity)
            with patch.object(panel._document, "load", wraps=panel._document.load) as load:
                panel.load_pdf(pdf, logical_key=scope / "main.tex")
                self.assertFalse(panel.last_load_reused)
                panel.load_pdf(pdf, logical_key=scope / "main.tex", content_identity=identity)
                panel.load_pdf(pdf, logical_key=scope / "other.tex", content_identity=identity)
                self.assertFalse(panel.last_load_reused)
                self.assertEqual(load.call_count, 3)
            old = capture_pdf_identity(pdf, scope)
            _write_zoom_pdf(pdf, mixed=True)
            panel.load_pdf(pdf, logical_key=scope / "other.tex", content_identity=old)
            self.assertFalse(panel.last_load_reused)
            self.assertIsNone(panel._loaded_identity)

    def test_search_escape_preserves_query_and_preedit_is_not_navigation(self):
        from PySide6.QtGui import QInputMethodEvent
        panel = PdfPanel()
        self.addCleanup(panel.close)
        self.addCleanup(panel.clear_pdf)
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "search.pdf"
            _write_zoom_pdf(pdf)
            panel.show()
            panel.load_pdf(pdf)
            QTest.qWait(160)
            panel.page_spin.setFocus()
            panel.show_pdf_search()
            panel.pdf_search_edit.setText("Synthetic")
            QApplication.sendEvent(panel.pdf_search_edit, QInputMethodEvent("\u4e2d", []))
            with patch.object(panel, "goto_pdf_search_result") as navigate:
                panel._search_enter()
                navigate.assert_not_called()
            QTest.keyClick(panel.pdf_search_edit, Qt.Key.Key_Escape)
            self.assertTrue(panel._search_row.isVisible())
            QApplication.sendEvent(panel.pdf_search_edit, QInputMethodEvent("", []))
            QTest.keyClick(panel.pdf_search_edit, Qt.Key.Key_Escape)
            self.assertFalse(panel._search_row.isVisible())
            self.assertEqual(panel.pdf_search_edit.text(), "Synthetic")
            self.assertTrue(panel.page_spin.hasFocus())

    def test_search_shortcut_from_sibling_widget_returns_focus_without_editing_it(self):
        from PySide6.QtWidgets import QWidget, QVBoxLayout
        window = QWidget()
        self.addCleanup(window.close)
        edit = QLineEdit("unchanged draft")
        panel = PdfPanel()
        self.addCleanup(panel.clear_pdf)
        layout = QVBoxLayout(window)
        layout.addWidget(edit)
        layout.addWidget(panel)
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "search.pdf"
            _write_zoom_pdf(pdf)
            panel.load_pdf(pdf)
            window.show()
            QTest.qWait(160)
            edit.setFocus()
            QTest.keyClick(edit, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            self.assertTrue(panel.pdf_search_edit.hasFocus())
            QTest.keyClick(panel.pdf_search_edit, Qt.Key.Key_Escape)
            self.assertTrue(edit.hasFocus())
            self.assertEqual(edit.text(), "unchanged draft")

    def test_search_enter_does_not_trigger_dialog_default_action(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout
        from PySide6.QtTest import QSignalSpy
        dialog = QDialog()
        self.addCleanup(dialog.close)
        panel = PdfPanel()
        self.addCleanup(panel.clear_pdf)
        default = QPushButton("Default action")
        default.setDefault(True)
        layout = QVBoxLayout(dialog)
        layout.addWidget(panel)
        layout.addWidget(default)
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "search.pdf"
            _write_zoom_pdf(pdf)
            panel.load_pdf(pdf)
            dialog.show()
            QTest.qWait(160)
            panel.show_pdf_search()
            panel.pdf_search_edit.setText("Synthetic")
            clicked = QSignalSpy(default.clicked)
            QTest.keyClick(panel.pdf_search_edit, Qt.Key.Key_Return)
            self.assertEqual(clicked.count(), 0)
            self.assertTrue(dialog.isVisible())

    def test_zoom_controls_preserve_effective_scale_page_and_anchor(self):
        from PySide6.QtPdfWidgets import QPdfView
        panel = PdfPanel()
        self.addCleanup(panel.close)
        self.addCleanup(panel.clear_pdf)
        if panel._view is None:
            self.skipTest("QtPdf is unavailable")
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "zoom-pages.pdf"
            _write_zoom_pdf(pdf)
            original = pdf.read_bytes()
            panel.resize(600, 500)
            panel.show()
            panel.load_pdf(pdf)
            QTest.qWait(160)
            self.assertEqual(panel._document.pageCount(), 3)
            for mode in (QPdfView.ZoomMode.FitToWidth, QPdfView.ZoomMode.FitInView,
                         QPdfView.ZoomMode.Custom):
                for page in (1, 2, 3):
                    for factor in (1 / 1.15, 1.15):
                        with self.subTest(mode=mode, page=page, factor=factor):
                            panel._view.setZoomMode(mode)
                            panel._view.setZoomFactor(1.0)
                            QTest.qWait(20)  # Settle raw fixture mode/scrollbar setup before navigation.
                            panel.jump_to_page(page)
                            QTest.qWait(20)
                            viewport = panel._view.viewport()
                            point = QPointF(viewport.width() / 2, viewport.height() * .4)
                            anchor = panel.pdf_position_for_viewport_point(point)
                            self.assertIsNotNone(anchor)
                            self.assertEqual(anchor[0], page)
                            before = panel._effective_zoom(page - 1)
                            panel.zoom_by(factor)
                            QTest.qWait(20)
                            self.assertAlmostEqual(panel._effective_zoom(page - 1), before * factor)
                            self.assertEqual(panel.current_page(), page)
                            # Locate the same document point after any viewport-size change.
                            left, top, _width, _height, zoom = panel._page_geometry(page - 1)
                            target_x = left + anchor[1] * zoom - viewport.width() / 2
                            target_y = top + anchor[2] * zoom - viewport.height() * .4
                            for bar, target in ((panel._view.horizontalScrollBar(), target_x),
                                                (panel._view.verticalScrollBar(), target_y)):
                                self.assertAlmostEqual(bar.value(), max(0, min(bar.maximum(), target)), delta=2)
            self.assertEqual(pdf.read_bytes(), original)

    def test_zoom_changes_rendered_marker_size_in_both_directions(self):
        from PySide6.QtGui import QImage
        from PySide6.QtPdfWidgets import QPdfView
        panel = PdfPanel()
        self.addCleanup(panel.close)
        self.addCleanup(panel.clear_pdf)
        if panel._view is None:
            self.skipTest("QtPdf is unavailable")

        def marker_bounds():
            image = panel._view.viewport().grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
            data, stride = image.constBits().tobytes(), image.bytesPerLine()
            xs, ys = [], []
            for y in range(image.height()):
                row = data[y * stride:y * stride + image.width() * 4]
                found = [x for x in range(image.width())
                         if row[x * 4] > 180 and row[x * 4 + 1] < 80 and row[x * 4 + 2] < 80]
                if found:
                    xs.extend((found[0], found[-1]))
                    ys.append(y)
            self.assertTrue(xs, "The actual PDF viewport must contain the red fixture marker")
            return min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1

        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "painted-zoom.pdf"
            _write_zoom_pdf(pdf, mixed=True)
            panel.resize(600, 500)
            panel.show()
            panel.load_pdf(pdf)
            QTest.qWait(160)
            for mode in (QPdfView.ZoomMode.FitToWidth, QPdfView.ZoomMode.FitInView,
                         QPdfView.ZoomMode.Custom):
                for factor in (1 / 1.15, 1.15):
                    with self.subTest(mode=mode, factor=factor):
                        panel._view.setZoomMode(mode)
                        panel._view.setZoomFactor(1.0)
                        QTest.qWait(20)
                        panel.jump_to_page(2)
                        QTest.qWait(120)
                        before = marker_bounds()
                        self.assertAlmostEqual(before[2], 120 * panel._effective_zoom(1), delta=2)
                        panel.zoom_by(factor)
                        QTest.qWait(120)
                        after = marker_bounds()
                        self.assertAlmostEqual(after[2], before[2] * factor, delta=2)
                        self.assertAlmostEqual(after[3], before[3] * factor, delta=2)
                        self.assertEqual(panel.current_page(), 2)

    def test_fit_modes_preserve_current_page_and_pending_zoom_yields_to_navigation(self):
        from PySide6.QtPdfWidgets import QPdfView
        from PySide6.QtCore import QCoreApplication, QEvent
        from shiboken6 import isValid
        panel = PdfPanel()
        self.addCleanup(lambda: panel.close() if isValid(panel) else None)
        if panel._view is None:
            self.skipTest("QtPdf is unavailable")
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "fit-pages.pdf"
            other = Path(directory) / "other.pdf"
            _write_zoom_pdf(pdf, mixed=True)
            _write_zoom_pdf(other)
            panel.resize(600, 500)
            panel.show()
            panel.load_pdf(pdf)
            QTest.qWait(160)
            for page in (1, 2, 3):
                for fit in (panel.fit_page, panel.fit_width):
                    with self.subTest(page=page, fit=fit.__name__):
                        panel._view.setZoomMode(QPdfView.ZoomMode.Custom)
                        panel._view.setZoomFactor(1.0)
                        QTest.qWait(20)
                        panel.jump_to_page(page)
                        fit()
                        QTest.qWait(20)
                        self.assertEqual(panel.current_page(), page)
                        point = QPointF(panel._view.viewport().width() / 2, panel._view.viewport().height() * .4)
                        self.assertEqual(panel.pdf_position_for_viewport_point(point)[0], page)
                        if fit == panel.fit_page:
                            left, top, width, height, _zoom = panel._page_geometry(page - 1)
                            x = left - panel._view.horizontalScrollBar().value()
                            y = top - panel._view.verticalScrollBar().value()
                            self.assertGreaterEqual(x, -1)
                            self.assertGreaterEqual(y, -1)
                            self.assertLessEqual(x + width, panel._view.viewport().width() + 1)
                            self.assertLessEqual(y + height, panel._view.viewport().height() + 1)
            for operation in (lambda: panel.jump_to_page(1), lambda: panel.jump_to_pdf_position(1, 100, 100),
                              lambda: panel.load_pdf(other), panel.clear_pdf):
                panel.load_pdf(pdf)
                QTest.qWait(160)
                panel.jump_to_page(2)
                panel.zoom_by(1.15)
                self.assertTrue(panel._zoom_anchor_timer.isActive())
                operation()
                self.assertFalse(panel._zoom_anchor_timer.isActive())
                self.assertIsNone(panel._zoom_anchor)
                with patch.object(panel, "_apply_zoom_anchor") as late:
                    QTest.qWait(20)
                    late.assert_not_called()
            panel.load_pdf(pdf)
            QTest.qWait(160)
            panel.zoom_by(1.15)
            with patch.object(panel, "_apply_zoom_anchor") as late:
                panel.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                self.assertFalse(isValid(panel))
                QTest.qWait(20)
                late.assert_not_called()

    def test_more_menu_has_native_keyboard_focus_and_immediate_popup(self):
        from PySide6.QtWidgets import QToolButton
        panel = PdfPanel()
        self.addCleanup(panel.close)
        self.assertEqual(panel._more_button.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.assertEqual(panel._more_button.popupMode(), QToolButton.ToolButtonPopupMode.InstantPopup)

    def test_overflow_actions_follow_disabled_controls_without_emitting_clicks(self):
        from PySide6.QtTest import QSignalSpy
        panel = PdfPanel()
        self.addCleanup(panel.close)
        buttons = (panel.pdf_search_button, panel.prev_page_button, panel.next_page_button, panel.fit_page_button,
                   panel.export_pdf_button, panel.reveal_pdf_button)
        actions = panel._more_button.menu().actions()
        self.assertEqual(len(actions), len(buttons))
        for button, action in zip(buttons, actions):
            with self.subTest(action=action.text()):
                clicked = QSignalSpy(button.clicked)
                self.assertFalse(button.isEnabled())
                self.assertFalse(action.isEnabled())
                action.trigger()
                self.assertEqual(clicked.count(), 0)
                button.setEnabled(True)
                self.assertTrue(action.isEnabled())
                action.trigger()
                self.assertEqual(clicked.count(), 1)
                button.setEnabled(False)
                self.assertFalse(action.isEnabled())
                action.trigger()
                self.assertEqual(clicked.count(), 1)

    def test_disabled_overflow_actions_cannot_bypass_button_click_guards(self):
        from PySide6.QtTest import QSignalSpy
        panel = PdfPanel()
        self.addCleanup(panel.close)
        buttons = (panel.prev_page_button, panel.next_page_button, panel.fit_page_button,
                   panel.export_pdf_button, panel.reveal_pdf_button)
        for button, action in zip(buttons, panel._more_button.menu().actions()):
            with self.subTest(action=action.text()):
                clicked = QSignalSpy(button.clicked)
                action.trigger()
                self.assertEqual(clicked.count(), 0)
                action.setEnabled(True)  # A stale menu action must still respect the real button.
                action.trigger()
                self.assertEqual(clicked.count(), 0)

    def test_deferred_reload_callbacks_are_cancelled_when_panel_is_destroyed(self) -> None:
        from PySide6.QtCore import QCoreApplication, QEvent
        from shiboken6 import isValid
        panel = PdfPanel()
        if panel._document is None:
            self.skipTest("QtPdf is unavailable")
        with TemporaryDirectory() as temp:
            pdf = Path(temp) / "synthetic.pdf"
            pdf.write_bytes(b"%PDF-1.4 synthetic lifetime fixture")
            with patch.object(panel, "_update_page_controls") as controls, patch.object(panel, "_restore_state") as restore:
                panel.load_pdf(pdf)
                panel._restore_state_later(panel._capture_state())
                panel.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                self.assertFalse(isValid(panel))
                controls.reset_mock()
                restore.reset_mock()
                QTest.qWait(180)
                controls.assert_not_called()
                restore.assert_not_called()

    def test_toolbar_widgets_exist_with_chinese_labels(self) -> None:
        panel = PdfPanel()

        self.assertIsInstance(panel.prev_page_button, QPushButton)
        self.assertIsInstance(panel.next_page_button, QPushButton)
        self.assertIsInstance(panel.page_spin, QSpinBox)
        self.assertIsInstance(panel.page_count_label, QLabel)
        self.assertIsInstance(panel.zoom_in_button, QPushButton)
        self.assertIsInstance(panel.zoom_out_button, QPushButton)
        self.assertIsInstance(panel.fit_width_button, QPushButton)
        self.assertIsInstance(panel.fit_page_button, QPushButton)
        self.assertIsInstance(panel.pdf_search_edit, QLineEdit)
        self.assertIsInstance(panel.pdf_search_prev_button, QPushButton)
        self.assertIsInstance(panel.pdf_search_next_button, QPushButton)
        self.assertIsInstance(panel.pdf_search_status, QLabel)

        self.assertEqual(panel.prev_page_button.text(), "")
        self.assertEqual(panel.prev_page_button.toolTip(), "上一页")
        self.assertEqual(panel.next_page_button.toolTip(), "下一页")
        self.assertEqual(panel.fit_width_button.toolTip(), "适合宽度")
        self.assertEqual(panel.fit_page_button.toolTip(), "适合页面")
        self.assertFalse(panel.prev_page_button.icon().isNull())
        self.assertEqual(panel.pdf_search_edit.placeholderText(), "搜索 PDF")
        self.assertEqual(panel.page_count_label.text(), "")

        self.assertGreaterEqual(panel.page_spin.minimum(), 1)
        for widget in (
            panel.prev_page_button,
            panel.next_page_button,
            panel.page_spin,
            panel.zoom_in_button,
            panel.zoom_out_button,
            panel.fit_width_button,
            panel.fit_page_button,
            panel.pdf_search_edit,
            panel.pdf_search_prev_button,
            panel.pdf_search_next_button,
            panel.export_pdf_button,
            panel.reveal_pdf_button,
        ):
            self.assertFalse(widget.isEnabled())
        self.assertEqual(panel.page_spin.accessibleName(), "PDF 页码")
        self.assertEqual(panel.pdf_search_edit.accessibleName(), "搜索 PDF")
        if hasattr(panel, "_empty_state"):
            self.assertIs(panel._stack.currentWidget(), panel._empty_state)
        panel.close()

    def test_jump_to_page_is_safe_without_document(self) -> None:
        panel = PdfPanel()
        # No PDF loaded yet; calling jump should not raise.
        panel.jump_to_page(1)
        panel.jump_to_page(5)
        self.assertEqual(panel.current_pdf, None)
        panel.close()

    def test_pdf_position_for_viewport_point_returns_none_without_pdf(self) -> None:
        from PySide6.QtCore import QPointF

        panel = PdfPanel()
        self.assertIsNone(panel.pdf_position_for_viewport_point(QPointF(10.0, 10.0)))
        panel.close()

    def test_double_click_emits_only_mapped_left_button_positions(self) -> None:
        panel = PdfPanel()
        self.addCleanup(panel.close)
        if panel._view is None:
            self.skipTest("QtPdf is unavailable")
        requested = Mock()
        panel.sourceRequested.connect(requested)
        with patch.object(panel, "pdf_position_for_viewport_point", return_value=(2, 30.0, 40.0)):
            QTest.mouseDClick(panel._view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(10, 20))
        requested.assert_called_once_with(2, 30.0, 40.0)
        requested.reset_mock()
        with patch.object(panel, "pdf_position_for_viewport_point", return_value=None):
            QTest.mouseDClick(panel._view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(10, 20))
        requested.assert_not_called()
        with patch.object(panel, "pdf_position_for_viewport_point", return_value=(2, 30.0, 40.0)):
            QTest.mouseDClick(panel._view.viewport(), Qt.MouseButton.RightButton, pos=QPoint(10, 20))
        requested.assert_not_called()

    def test_reverse_mapping_rejects_page_margins_and_inter_page_gaps(self) -> None:
        panel = PdfPanel()
        self.addCleanup(panel.close)
        if panel._view is None:
            self.skipTest("QtPdf is unavailable")
        document = Mock()
        document.pageCount.return_value = 2
        document.pagePointSize.return_value = QSizeF(100, 200)
        with (
            patch.object(panel, "_document", document),
            patch.object(panel, "_page_geometry", side_effect=lambda page: (10, 20 + page * 210, 100, 200, 1)),
        ):
            for point in (QPointF(5, 50), QPointF(115, 50), QPointF(50, 225)):
                self.assertIsNone(panel.pdf_position_for_viewport_point(point))
            self.assertEqual(panel.pdf_position_for_viewport_point(QPointF(50, 250)), (2, 40.0, 20.0))

    def test_logical_key_preserves_view_state_when_physical_pdf_changes(self) -> None:
        panel = PdfPanel()
        state = PdfViewState(page=2, horizontal=31, vertical=418, zoom_factor=1.4, zoom_mode=object())
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            preview = Path(directory) / "preview" / "main.pdf"
            final = Path(directory) / "final" / "main.pdf"
            preview.parent.mkdir()
            final.parent.mkdir()
            preview.touch()
            final.touch()
            panel.current_pdf = preview
            panel.current_logical_key = root
            panel._document = Mock()
            panel._document.pageCount.return_value = 0

            with (
                patch.object(panel, "_capture_state", return_value=state) as capture,
                patch.object(panel, "_restore_state_later") as restore,
                patch("app.gui.pdf_panel.QTimer.singleShot"),
            ):
                panel.load_pdf(final, logical_key=root)

            capture.assert_called_once_with()
            restore.assert_called_once_with(state)
            self.assertEqual(panel.current_pdf, final)
            self.assertEqual(panel.current_logical_key, root)
        panel.close()

    def test_default_logical_key_keeps_physical_path_behavior(self) -> None:
        panel = PdfPanel()
        with TemporaryDirectory() as directory:
            first = Path(directory) / "first.pdf"
            second = Path(directory) / "second.pdf"
            first.touch()
            second.touch()
            panel.current_pdf = first
            panel.current_logical_key = first
            panel._document = Mock()
            panel._document.pageCount.return_value = 0

            with (
                patch.object(panel, "_capture_state") as capture,
                patch.object(panel, "_restore_state_later") as restore,
                patch("app.gui.pdf_panel.QTimer.singleShot"),
            ):
                panel.load_pdf(second)

            capture.assert_not_called()
            restore.assert_called_once_with(None)
            self.assertEqual(panel.current_logical_key, second)

            panel._document.pageCount.return_value = 0
            panel.clear_pdf()
            self.assertIsNone(panel.current_pdf)
            self.assertIsNone(panel.current_logical_key)
        panel.close()
