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


class PdfPanelToolbarTests(TestCase):
    def setUp(self) -> None:
        _app()

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
        self.assertEqual(panel.page_count_label.text(), "/ 0")

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
