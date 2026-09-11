from __future__ import annotations

import os
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt, QEvent
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolBar

from app.core.settings import AppSettings
from app.gui.main_window import MainWindow
from app.gui.theme import (
    CJK_SANS_FONT_CANDIDATES,
    CJK_SERIF_FONT_CANDIDATES,
    COLOR_EDITOR,
    COLOR_SYNTAX_COMMENT,
    COLOR_SYNTAX_OPTION,
    COLOR_TEXT_FAINT,
    LATIN_MONO_FONT_CANDIDATES,
    UI_LATIN_SANS_FONT_CANDIDATES,
    apply_theme,
    editor_font,
    heading_font,
    stylesheet,
    ui_font,
)


_TEMP = TemporaryDirectory()
_COUNTER = count()


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
        apply_theme(instance)
    return instance


class WorkbenchVisualSmokeTests(TestCase):
    def test_recovery_draft_review_buttons_fit_large_font(self):
        from app.gui.project_recovery_dialog import RecoveryDraftDialog
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        dialog = RecoveryDraftDialog(window)
        try:
            for size in (12, 18):
                font = dialog.font()
                font.setPointSize(size)
                dialog.setFont(font)
                dialog.resize(760, 560)
                dialog.show()
                application.processEvents()
                for control in (dialog.choose_button, dialog.apply_button, dialog.close_button):
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().topLeft())))
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().bottomRight())))
                self.assertTrue(dialog.preview.isReadOnly())
                self.assertFalse(dialog.apply_button.isEnabled())
        finally:
            dialog.reject()
            dialog.deleteLater()
            window.close()
            window.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_checkpoint_review_actions_and_close_fit_with_large_font(self):
        from app.gui.project_checkpoint_dialog import ProjectCheckpointDialog
        from tests.test_gui_editor import isolated_settings
        application = _app()
        window = MainWindow(settings_store=isolated_settings())
        dialog = ProjectCheckpointDialog(window, restore=True)
        try:
            dialog.status.setText("已验证合成检查点；请审阅相对路径和独立草稿，再选择新目录。")
            for size in (12, 18):
                font = dialog.font()
                font.setPointSize(size)
                dialog.setFont(font)
                dialog.resize(760, 560)
                dialog.show()
                application.processEvents()
                for control in (dialog.open_button, dialog.target_button, dialog.action_button, dialog.close_button):
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().topLeft())))
                    self.assertTrue(dialog.rect().contains(control.mapTo(dialog, control.rect().bottomRight())))
                self.assertTrue(dialog.preview.isReadOnly())
                self.assertFalse(dialog.action_button.isEnabled())
        finally:
            dialog.reject()
            dialog.deleteLater()
            window.close()
            window.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_source_repair_mapping_controls_and_cancel_remain_reachable(self):
        from types import SimpleNamespace
        from app.core.blocks.table_import import read_csv_text
        from app.gui.blocks.source_repair_dialog import SourceTableMappingDialog
        from PySide6.QtWidgets import QDialogButtonBox, QScrollArea
        application = _app()
        local = read_csv_text("Key,Value\nA,10\n")
        snapshot = SimpleNamespace(local_tables={"t": local}, blocks={"t": {"alias": "合成来源表格"}})
        dialog = SourceTableMappingDialog(None, snapshot, "t", None, None)
        try:
            for size in (12, 18):
                font = dialog.font()
                font.setPointSize(size)
                dialog.setFont(font)
                dialog.resize(760, 600)
                dialog.show()
                application.processEvents()
                scroll = dialog.findChild(QScrollArea)
                scroll.ensureWidgetVisible(dialog.load_button)
                application.processEvents()
                self.assertTrue(scroll.viewport().rect().contains(
                    dialog.load_button.mapTo(scroll.viewport(), dialog.load_button.rect().center())))
                self.assertTrue(dialog.rect().contains(dialog.preview_button.mapTo(dialog, dialog.preview_button.rect().center())))
                cancel = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel)
                self.assertTrue(dialog.rect().contains(cancel.mapTo(dialog, cancel.rect().center())))
            self.assertFalse(dialog.preview_button.isEnabled())
            dialog.encoding.setCurrentIndex(1)
            self.assertIsNone(dialog.parsed)
            self.assertIsNone(dialog.candidate)
        finally:
            dialog.close()
            dialog.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_merge_preview_controls_are_reachable_and_changes_require_a_fresh_preview(self):
        from app.core.blocks.source_merge import merge_three_way
        from app.gui.blocks.merge_dialog import MergeDialog
        from tests.test_source_merge import table
        from PySide6.QtWidgets import QDialogButtonBox
        application = _app()
        result = merge_three_way(table({"r1": {"a": "base", "b": "keep"}}),
                                 table({"r1": {"a": "remote", "b": "keep"}}),
                                 table({"r1": {"a": "local", "b": "keep"}}))
        before = result.data.to_content_dict()
        dialog = MergeDialog(result)
        try:
            for point_size in (12, 18):
                font = dialog.font()
                font.setPointSize(point_size)
                dialog.setFont(font)
                dialog.resize(760, 640)
                dialog.show()
                application.processEvents()
                for button in (dialog.preview_button, dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)):
                    self.assertTrue(dialog.rect().contains(button.mapTo(dialog, button.rect().center())))
                self.assertTrue(dialog.preview.isReadOnly())
            dialog._manual_buttons[0].setChecked(True)
            self.assertFalse(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
            dialog.preview_button.click()
            self.assertIn('"value": ""', dialog.preview.toPlainText())
            dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
            self.assertEqual(dialog.result.data.cell("r1", "a").value, "")
            self.assertEqual(dialog.result.data.cell("r1", "b").value, "keep")
            self.assertEqual(result.data.to_content_dict(), before)
        finally:
            dialog.close()
            dialog.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_table_draft_controls_are_reachable_in_a_narrow_large_font_workspace(self):
        from app.core.blocks.registry import BlockRegistry, CreateBlockInput
        from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow
        from app.gui.blocks.project_session import ProjectSession
        from app.gui.blocks.workspace_widget import BlockWorkspaceWidget
        application = _app()
        registry = BlockRegistry()
        block = registry.create(CreateBlockInput(type="table", alias="合成的长名称表格",
            content=TableData(columns=[ColumnSpec("c1", "Value")],
                rows=[TableRow("r1", {"c1": Cell("text", "before")})]).to_content_dict()))
        session = ProjectSession(registry=registry)
        workspace = BlockWorkspaceWidget(session)
        try:
            font = workspace.font()
            font.setPointSizeF(18)
            workspace.setFont(font)
            workspace.resize(300, 380)
            workspace.show()
            workspace.open_table(block.id)
            workspace.table_editor.table.item(0, 0).setText("unapplied")
            application.processEvents()
            scroll = workspace.tabs.widget(1)
            for button in (workspace.table_apply_button, workspace.table_discard_button):
                scroll.ensureWidgetVisible(button)
                QTest.qWait(20)
                rect = button.rect()
                rect.moveTopLeft(button.mapTo(scroll.viewport(), rect.topLeft()))
                self.assertTrue(scroll.viewport().rect().contains(rect), (rect, scroll.viewport().rect()))
            self.assertEqual(block.content["rows"][0]["cells"]["c1"]["value"], "before")
            self.assertEqual(session.undo_stack.count(), 0)
            self.assertIsNone(session.compile_manager)
        finally:
            session.shutdown()
            workspace.close()
            workspace.deleteLater()
            session.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_button_flow_wraps_whole_buttons_without_overlap(self):
        from app.gui.responsive.helpers import ButtonFlowLayout
        from PySide6.QtWidgets import QPushButton, QWidget
        application = _app()
        widget = QWidget()
        flow = ButtonFlowLayout(widget)
        buttons = [QPushButton(text) for text in ("组合为 Row", "组合为 Grid", "取消组合", "撤销")]
        for button in buttons:
            flow.addWidget(button)
        try:
            widget.show()
            for width in (260, 640, 280):
                widget.resize(width, 400)
                application.processEvents()
                for index, button in enumerate(buttons):
                    self.assertTrue(widget.rect().contains(button.geometry()))
                    self.assertGreaterEqual(button.width(), button.sizeHint().width())
                    for other in buttons[index + 1:]:
                        self.assertFalse(button.geometry().intersects(other.geometry()))
                if width == 260:
                    self.assertGreater(buttons[-1].y(), buttons[0].y())
        finally:
            widget.close()
            widget.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_block_preview_switch_preserves_widgets_and_focused_editor(self):
        from app.gui.blocks.workspace_widget import BlockPreviewArea
        from PySide6.QtWidgets import QLineEdit, QWidget, QVBoxLayout
        application = _app()
        editor, pdf = QWidget(), QWidget()
        edit = QLineEdit()
        QVBoxLayout(editor).addWidget(edit)
        area = BlockPreviewArea(editor, pdf)
        parents = editor.parentWidget(), pdf.parentWidget()
        try:
            area.resize(600, 500)
            area.show()
            application.processEvents()
            area.pdf_button.click()
            self.assertTrue(editor.isHidden())
            area.resize(1400, 500)
            application.processEvents()
            self.assertFalse(editor.isHidden())
            edit.setFocus()
            QTest.keyClicks(edit, "pending draft")
            area.resize(600, 500)
            application.processEvents()
            self.assertFalse(editor.isHidden())
            self.assertTrue(pdf.isHidden())
            self.assertIs(application.focusWidget(), edit)
            self.assertEqual(edit.text(), "pending draft")
            self.assertEqual((editor.parentWidget(), pdf.parentWidget()), parents)
        finally:
            area.close()
            area.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_first_window_registers_with_new_scale_manager(self):
        application = _app()
        previous = getattr(application, "ui_scale_manager", None)
        if previous is not None:
            del application.ui_scale_manager
        window = None
        try:
            window = MainWindow(settings_store=AppSettings(QSettings(
                str(Path(_TEMP.name) / f"first-scale-{next(_COUNTER)}.ini"), QSettings.Format.IniFormat)))
            self.assertIn(window, application.ui_scale_manager._windows)
        finally:
            if window is not None:
                window.close()
                window.deleteLater()
                application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            if previous is not None:
                application.ui_scale_manager = previous

    def test_block_layout_and_inspector_fit_narrow_scroll_containers(self):
        from app.gui.blocks.project_session import ProjectSession
        from app.gui.blocks.workspace_widget import BlockWorkspaceWidget
        from app.gui.blocks.inspector import BlockInspector
        application = _app()
        session = ProjectSession()
        workspace = BlockWorkspaceWidget(session)
        inspector = BlockInspector(session)
        try:
            for widget in (workspace, inspector):
                widget.resize(280, 300)
                widget.show()
                application.processEvents()
                self.assertLessEqual(widget.width(), 280)
                self.assertLessEqual(widget.height(), 300)
            self.assertIsNone(session.compile_manager)
        finally:
            session.shutdown()
            for widget in (workspace, inspector):
                widget.close()
                widget.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_profile_dialog_keyboard_and_scroll_access_at_all_scales(self):
        from app.gui.project_profile_dialog import ProjectProfileDialog
        from app.gui.theme.ui_scale_manager import UiScaleManager
        from PySide6.QtWidgets import QDialogButtonBox
        application = _app()
        manager = getattr(application, "ui_scale_manager", None)
        if manager is None:
            manager = UiScaleManager(application)
            application.ui_scale_manager = manager
        previous = manager.scale
        with TemporaryDirectory() as directory:
            dialog = ProjectProfileDialog(Path(directory).resolve())
            try:
                dialog.resize(520, 480)
                dialog.show()
                for scale in (0.9, 1.0, 1.1, 1.25, 1.5):
                    manager.apply_scale(scale)
                    application.processEvents()
                    dialog.word_max.setFocus()
                    dialog.word_max.selectAll()
                    QTest.keyClicks(dialog.word_max, "234")
                    QTest.keyClick(dialog.word_max, Qt.Key.Key_Tab)
                    application.processEvents()
                    self.assertEqual(dialog.word_max.text(), "234")
                    self.assertIsNotNone(application.focusWidget())
                    for kind in (QDialogButtonBox.StandardButton.Save, QDialogButtonBox.StandardButton.Cancel):
                        button = dialog.buttons.button(kind)
                        self.assertTrue(button.isVisible())
                        self.assertTrue(dialog.rect().contains(button.mapTo(dialog, button.rect().center())))
                QTest.keyClick(dialog, Qt.Key.Key_Escape)
                self.assertFalse((Path(directory) / ".icstex").exists())
            finally:
                dialog.close()
                manager.apply_scale(previous)

    def test_destroyed_welcome_page_is_disconnected_from_scale_manager(self) -> None:
        import sys
        from unittest.mock import patch
        from PySide6.QtCore import QCoreApplication
        from shiboken6 import isValid
        from app.gui.theme.ui_scale_manager import UiScaleManager
        from app.gui.welcome_page import WelcomePage

        application = _app()
        if not hasattr(application, "ui_scale_manager"):
            application.ui_scale_manager = UiScaleManager(application)
        with patch.object(sys, "excepthook") as errors:
            for _ in range(5):
                page = WelcomePage()
                page.show()
                application.processEvents()
                page.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                self.assertFalse(isValid(page))
                application.ui_scale_manager.scale_changed.emit(1.25)
                application.processEvents()
            errors.assert_not_called()

    def test_formula_and_table_editor_layout_and_keyboard_flow(self) -> None:
        from app.gui.formula_dialog import FormulaDialog
        from app.gui.insert_panel import TableDialog
        from app.gui.math_keyboard import MathKeyButton

        application = _app()
        formula = FormulaDialog(None, "", 0, 0, seed_text=r"\(x=\)")
        table = TableDialog()
        try:
            for width, height in ((920, 720), (800, 720), (1040, 720), (920, 720)):
                formula.resize(width, height)
                formula.show()
                application.processEvents()
                self.assertEqual(formula.size().width(), width)
                self.assertLessEqual(formula.size().height(), height)
                self.assertTrue(formula._ok_button.isVisible())
                self.assertGreater(formula.keyboard.stack.width(), 100)
                self.assertIsNotNone(formula.keyboard.stack.parentWidget())
                self.assertFalse(formula.grab().isNull())
            actions = {button.action: button for button in formula.keyboard.findChildren(MathKeyButton)}
            self.assertNotIn("apply", actions)
            self.assertTrue(all(button.accessibleName() for button in actions.values()))
            formula.keyboard._emit("toggle:abc")
            application.processEvents()
            self.assertLessEqual(formula.width(), 920)
            self.assertLessEqual(formula.height(), 720)
            self.assertEqual(formula.keyboard.stack.currentWidget(), formula.keyboard.letters_row)
            formula.keyboard._emit("toggle:abc")
            self.assertEqual(formula.keyboard.stack.currentWidget(), formula.keyboard._base_page)
            actions["structure:fraction"].click()
            QTest.keyClicks(formula.visual_edit, "a")
            QTest.keyClick(formula.visual_edit, Qt.Key.Key_Tab)
            QTest.keyClicks(formula.visual_edit, "b")
            QTest.keyClick(formula.visual_edit, Qt.Key.Key_Return)
            self.assertEqual(formula.preview_edit.toPlainText(), r"\(x=\frac{a}{b}\)")
            self.assertIsNone(formula.plan())
            formula.source_mode_check.setChecked(True)
            self.assertFalse(formula.keyboard.isVisible())
            formula.source_mode_check.setChecked(False)

            table.resize(840, 660)
            table.show()
            table.paste_clipboard_text("Name\tValue\nA\t0\nB\t1")
            application.processEvents()
            self.assertLessEqual(table.height(), 660)
            self.assertEqual(table._cell_text(1, 1), "0")
            self.assertFalse(table.grab().isNull())
        finally:
            formula.close()
            table.close()
            formula.deleteLater()
            table.deleteLater()
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_font_roles_resolve_expected_latin_and_chinese_families(self) -> None:
        _app()
        available = set(QFontDatabase.families())
        expected_ui_latin = next(
            (family for family in UI_LATIN_SANS_FONT_CANDIDATES if family in available),
            None,
        )
        expected_mono_latin = next(
            (family for family in LATIN_MONO_FONT_CANDIDATES if family in available),
            None,
        )
        expected_sans_cjk = next(
            (family for family in CJK_SANS_FONT_CANDIDATES if family in available),
            None,
        )
        expected_serif_cjk = next(
            (family for family in CJK_SERIF_FONT_CANDIDATES if family in available),
            None,
        )

        expected_roles = (
            (ui_font(), expected_ui_latin, expected_sans_cjk),
            (editor_font(), expected_mono_latin, expected_serif_cjk),
            (heading_font(), expected_ui_latin, expected_serif_cjk),
        )
        for font, expected_latin, expected_cjk in expected_roles:
            families = font.families()
            if expected_latin is not None:
                self.assertEqual(families[0], expected_latin)
            if expected_cjk is not None:
                self.assertIn(expected_cjk, families)
                if expected_latin is not None:
                    self.assertGreater(families.index(expected_cjk), families.index(expected_latin))

        qss = stylesheet()
        for family in (expected_ui_latin, expected_mono_latin, expected_sans_cjk, expected_serif_cjk):
            if family is not None:
                self.assertIn(f'"{family}"', qss)

    def test_small_text_theme_colors_meet_aa_contrast(self) -> None:
        for color in (COLOR_TEXT_FAINT, COLOR_SYNTAX_OPTION, COLOR_SYNTAX_COMMENT):
            self.assertGreaterEqual(_contrast_ratio(color, COLOR_EDITOR), 4.5)

    def test_supported_window_sizes_render_without_black_toolbar_or_overlap(self) -> None:
        application = _app()
        for width, height in ((1440, 900), (1280, 720), (1100, 720)):
            settings = AppSettings(
                QSettings(
                    str(Path(_TEMP.name) / f"visual-{next(_COUNTER)}.ini"),
                    QSettings.Format.IniFormat,
                )
            )
            window = MainWindow(settings_store=settings)
            window.resize(width, height)
            window.show()
            application.processEvents()

            toolbar = window.findChild(QToolBar, "mainToolbar")
            self.assertIsNotNone(toolbar)
            assert toolbar is not None
            self.assertGreater(toolbar.height(), 0)
            self.assertGreaterEqual(window.main_splitter.widget(0).width(), 430)
            self.assertGreaterEqual(window.main_splitter.widget(1).width(), 360)

            compile_button = toolbar.widgetForAction(window.compile_action)
            self.assertIsNotNone(compile_button)
            assert compile_button is not None
            image = compile_button.grab().toImage()
            self.assertFalse(image.isNull())
            dark_pixels = 0
            sampled = 0
            for x in range(0, image.width(), 3):
                for y in range(0, image.height(), 3):
                    color = image.pixelColor(x, y)
                    sampled += 1
                    if color.red() < 20 and color.green() < 20 and color.blue() < 20:
                        dark_pixels += 1
            self.assertLess(dark_pixels, max(1, sampled // 3))

            frame = window.grab()
            self.assertFalse(frame.isNull())
            self.assertEqual(frame.size().width(), width)
            self.assertEqual(frame.size().height(), height)
            window.close()


def _contrast_ratio(foreground: str, background: str) -> float:
    light, dark = sorted((_relative_luminance(foreground), _relative_luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


class AppUpdateVisualTests(TestCase):
    def test_update_dialog_chinese_content_and_actions_fit(self) -> None:
        from app.gui.update_dialog import AppUpdateDialog
        application = _app()
        dialog = AppUpdateDialog()
        try:
            dialog.set_state(available=False, automatic=False,
                             message="当前是源码开发模式，未启用应用内更新。请在带更新器的正式安装包中使用。")
            for width in (480, 600):
                dialog.resize(width, 360)
                dialog.show()
                application.processEvents()
                self.assertEqual(dialog.width(), width)
                self.assertTrue(dialog.rect().contains(dialog.check_button.geometry()))
                self.assertTrue(dialog.rect().contains(dialog.automatic.geometry()))
                self.assertFalse(dialog.check_button.isEnabled())
                self.assertFalse(dialog.automatic.isChecked())
                self.assertFalse(dialog.grab().isNull())
            dialog.set_state(available=True, automatic=True, message="发现可用更新，请在原生更新窗口查看并确认下载。",
                             source="更新源：updates.example.org", channel="Beta 通道")
            self.assertTrue(dialog.check_button.isEnabled())
            self.assertTrue(dialog.automatic.isChecked())
            dialog.set_state(available=True, automatic=False, message="更新正在进行。", checking=True)
            application.processEvents()
            self.assertEqual(dialog.check_button.text(), "查看更新进度")
            self.assertTrue(dialog.rect().contains(dialog.check_button.geometry()))
        finally:
            dialog.close()
            dialog.deleteLater()
