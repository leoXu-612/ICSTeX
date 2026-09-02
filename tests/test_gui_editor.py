from __future__ import annotations

from dataclasses import replace
import os
import time
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QMimeData, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDropEvent, QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea

from app.core.compiler import BuildPurpose, CompileManager, CompileOutcome, CompileResult
from app.core.formula_input import (
    FormulaDraft,
    FormulaMode,
    apply_formula_template,
    final_edit_plan,
    parse_document_selection,
)
from app.core.log_parser import LaTeXError
from app.core.pdf_state import PdfFreshness
from app.core.preview_state import PreviewFreshness
from app.core.settings import AppSettings
from app.core.latex_tools import LaTeXEngine, LaTeXToolchain
from app.core.latex_insertions import (
    HYPERLINK_PACKAGES,
    FigureLayout,
    FigureLayoutItem,
    FigureLayoutSpec,
)
from app.gui.diagnostics_panel import DiagnosticsPanel
from app.gui.environment_doctor_dialog import EnvironmentDoctorDialog
from app.gui.find_replace import FindReplaceBar
from app.gui.formula_dialog import FormulaDialog
from app.gui.insert_panel import FigureDialog, FigureLayoutDialog, HyperlinkDialog, TableDialog
from app.gui.latex_editor import LaTeXEditor
from app.gui.main_window import EditorTab, MainWindow
from app.gui.project_panels import BibEntryDialog, BibImportDialog, ProjectWizardDialog
from app.gui.settings_dialog import SettingsDialog
from app.gui.theme import apply_theme
from app.gui.toolbox_navigation import ToolboxNavigation
from app.gui.welcome_page import WelcomePage
from app.gui.widgets import AutoCompileToggle

_SETTINGS_TEMP = TemporaryDirectory()
_SETTINGS_COUNTER = count()


def app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
        apply_theme(instance)
    return instance


def isolated_settings() -> AppSettings:
    settings_file = Path(_SETTINGS_TEMP.name) / f"settings-{next(_SETTINGS_COUNTER)}.ini"
    return AppSettings(QSettings(str(settings_file), QSettings.Format.IniFormat))


def wait_until(predicate, timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    QApplication.processEvents()
    return predicate()


class GuiEditorTests(TestCase):
    def setUp(self) -> None:
        app()

    def test_editor_smoke_and_line_number_width(self) -> None:
        editor = LaTeXEditor("one\ntwo")

        self.assertEqual(editor.blockCount(), 2)
        self.assertGreater(editor.line_number_area_width(), 0)
        self.assertIsNotNone(editor.highlighter)
        self.assertEqual(editor.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)

    def test_export_and_reveal_pdf(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        self.assertEqual(window.export_pdf_action.text(), "导出 PDF")
        self.assertIn("PDF", window.reveal_pdf_action.text())

        # Without a successful PDF both actions are disabled and safe no-ops.
        self.assertFalse(window.export_pdf_action.isEnabled())
        self.assertFalse(window.reveal_pdf_action.isEnabled())
        self.assertFalse(window.pdf_panel.export_pdf_button.isEnabled())
        self.assertFalse(window.pdf_panel.reveal_pdf_button.isEnabled())
        self.assertFalse(window.export_pdf())
        with patch("app.gui.main_window.subprocess.Popen") as popen, patch(
            "app.gui.main_window.QDesktopServices.openUrl"
        ) as open_url:
            window.reveal_pdf()
        popen.assert_not_called()
        open_url.assert_not_called()

        with TemporaryDirectory() as tmp:
            tex = Path(tmp) / "main.tex"
            tex.write_text("x", encoding="utf-8")
            source = Path(tmp) / "main.pdf"
            source.write_bytes(b"%PDF-1.4 fake")
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            tab = EditorTab(editor=window._make_editor("x"), path=tex)
            window._add_tab(tab, tex.name)
            window.pdf_state.begin_build(tex, 1)
            window.pdf_state.finish_build(tex, 1, CompileOutcome.SUCCESS, pdf_file=source)
            window._update_pdf_action_state()
            self.assertTrue(window.export_pdf_action.isEnabled())
            self.assertTrue(window.pdf_panel.reveal_pdf_button.isEnabled())
            self.assertEqual(window.pdf_panel.freshness_label.text(), "PDF 已是最新")

            exported = Path(tmp) / "exported"
            with patch(
                "app.gui.main_window.QFileDialog.getSaveFileName",
                return_value=(str(exported), ""),
            ):
                self.assertTrue(window.export_pdf())
            self.assertEqual(exported.with_suffix(".pdf").read_bytes(), b"%PDF-1.4 fake")

            with patch("app.gui.main_window.subprocess.Popen") as popen, patch(
                "app.gui.main_window.QDesktopServices.openUrl"
            ) as open_url:
                window.reveal_pdf()
            if popen.called:
                args = popen.call_args.args[0]
                self.assertIsInstance(args, list)
                self.assertNotIn("shell", popen.call_args.kwargs)
            else:
                open_url.assert_called_once()

    def test_export_pdf_rejects_empty_and_rebuilds_when_stale(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window._watch_file = lambda _path: None  # type: ignore[method-assign]

        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "main.tex"
            source.write_text("x", encoding="utf-8")
            tab = EditorTab(editor=window._make_editor("x"), path=source)
            window._add_tab(tab, source.name)

            # Zero-byte PDF: not a valid successful build, actions stay disabled.
            empty_pdf = Path(tmp) / "empty.pdf"
            empty_pdf.write_bytes(b"")
            window.pdf_state.begin_build(source, 1)
            window.pdf_state.finish_build(source, 1, CompileOutcome.SUCCESS, pdf_file=empty_pdf)
            window._update_pdf_action_state()
            self.assertFalse(window.export_pdf_action.isEnabled())
            with patch("app.gui.main_window.QFileDialog.getSaveFileName") as dialog:
                self.assertFalse(window.export_pdf())
            dialog.assert_not_called()

            # A stale PDF is never copied: export queues a proper original-image build.
            pdf = Path(tmp) / "main.pdf"
            pdf.write_bytes(b"%PDF-1.4 old")
            window.pdf_state.begin_build(source, 2)
            window.pdf_state.finish_build(source, 2, CompileOutcome.SUCCESS, pdf_file=pdf)
            window.pdf_state.mark_edited(source)
            window._update_pdf_action_state()
            self.assertTrue(window.export_pdf_action.isEnabled())
            self.assertEqual(window.pdf_panel.freshness_label.text(), "源码已修改，PDF 待更新")

            exported = Path(tmp) / "exported"
            tab.manager = window.create_compile_manager(source)
            with patch.object(tab.manager, "compile_async") as compile_async, patch(
                "app.gui.main_window.QFileDialog.getSaveFileName",
                return_value=(str(exported), ""),
            ):
                self.assertTrue(window.export_pdf())
            compile_async.assert_called_once_with(BuildPurpose.FINAL)
            self.assertFalse(exported.with_suffix(".pdf").exists())
            pending = window.pdf_export.pending_for(source)
            self.assertIsNotNone(pending)
            assert pending is not None
            self.assertEqual(pending.target, exported.with_suffix(".pdf").resolve())

    def test_main_window_smoke(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        self.assertEqual(window.windowTitle(), "ICSTeX")
        self.assertEqual(window.error_table.columnCount(), 3)
        self.assertEqual(window.engine_selector.count(), 4)
        self.assertEqual(window.current_engine, LaTeXEngine.AUTO)
        self.assertEqual(window.sidebar_tabs.count(), 9)
        self.assertIsInstance(window.toolbox_navigation, ToolboxNavigation)
        self.assertEqual(window.sidebar_tabs.tabText(0), "文件")
        self.assertEqual(window.sidebar_tabs.tabText(1), "大纲")
        self.assertEqual(window.sidebar_tabs.tabText(2), "搜索")
        self.assertEqual(window.sidebar_tabs.tabText(3), "图片")
        self.assertEqual(window.sidebar_tabs.tabText(4), "历史")
        self.assertEqual(window.sidebar_tabs.tabText(5), "插入")
        self.assertEqual(window.sidebar_tabs.tabText(6), "模板")
        self.assertEqual(window.sidebar_tabs.tabText(7), "引用")
        self.assertEqual(window.sidebar_tabs.tabText(8), "标签")
        self.assertTrue(window.toolbox_navigation.navigationButton(0).isChecked())
        self.assertEqual(window.toolbox_navigation.navigationButton(0).toolTip(), "项目文件")
        self.assertEqual(Path(window.model.filePath(window.tree.rootIndex())), Path.home())
        self.assertEqual(window.tree.accessibleName(), "项目文件")
        self.assertIn("effective", window.word_count_labels)
        self.assertIn("numbers", window.word_count_labels)
        self.assertIsInstance(window.word_count_panel, QScrollArea)
        self.assertGreaterEqual(window.word_count_labels["effective"].minimumHeight(), 28)
        self.assertIsInstance(window.find_replace_bar, FindReplaceBar)
        self.assertIsInstance(window.welcome_page, WelcomePage)
        self.assertIsInstance(window.diagnostic_panel, DiagnosticsPanel)
        self.assertEqual(window.source_stack.currentWidget(), window.welcome_page)
        self.assertEqual(window.main_splitter.count(), 2)
        self.assertEqual(window.vertical_splitter.count(), 2)
        self.assertFalse(window.vertical_splitter.isCollapsible(0))
        self.assertFalse(window.vertical_splitter.isCollapsible(1))
        self.assertTrue(window.toolbox_dock.isHidden())
        self.assertFalse(window.toolbox_action.isChecked())
        window.toolbox_action.setChecked(True)
        self.assertFalse(window.toolbox_dock.isHidden())
        window.toolbox_action.setChecked(False)
        self.assertTrue(window.toolbox_dock.isHidden())
        self.assertTrue(hasattr(window.pdf_panel, "page_spin"))
        if window.pdf_panel._view is not None and window.pdf_panel._search_model is not None:
            self.assertIs(window.pdf_panel._view.searchModel(), window.pdf_panel._search_model)
        self.assertTrue(hasattr(window, "settings_action"))
        self.assertTrue(hasattr(window, "stop_compile_action"))
        self.assertTrue(hasattr(window, "health_check_action"))
        self.assertTrue(hasattr(window, "environment_doctor_action"))
        self.assertTrue(hasattr(window, "feedback_bundle_action"))
        self.assertTrue(hasattr(window, "user_guide_action"))
        self.assertGreaterEqual(window.templates_panel.template_combo.count(), 9)
        insert_labels = {button.text() for button in window.insert_panel.findChildren(QPushButton)}
        self.assertIn("章节标题", insert_labels)
        self.assertIn("分段函数", insert_labels)
        self.assertIn("图片布局", insert_labels)
        self.assertEqual(window.welcome_page.guide_button.text(), "新手导引")
        self.assertTrue(hasattr(window, "auto_compile_toggle"))
        self.assertIsInstance(window.auto_compile_toggle, AutoCompileToggle)
        self.assertFalse(window.stop_compile_action.isEnabled())
        for action in (
            window.save_action,
            window.save_as_action,
            window.compile_action,
            window.clean_build_action,
            window.full_rebuild_action,
            window.health_check_action,
            window.word_count_action,
            window.find_action,
            window.replace_action,
            window.sync_pdf_action,
        ):
            self.assertFalse(action.isEnabled())
        self.assertEqual(window.status_engine_label.text(), "Auto")
        self.assertEqual(window.auto_compile_toggle.isChecked(), window.auto_compile_action.isChecked())
        window.auto_compile_toggle.setChecked(False)
        self.assertFalse(window.auto_compile_action.isChecked())
        window.auto_compile_action.setChecked(True)
        self.assertTrue(window.auto_compile_toggle.isChecked())
        self.assertEqual(window.status_auto_label.text(), "自动编译")
        window.close()

    def test_document_actions_follow_editor_availability(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        window.new_document()
        for action in (
            window.save_action,
            window.save_as_action,
            window.compile_action,
            window.clean_build_action,
            window.full_rebuild_action,
            window.health_check_action,
            window.word_count_action,
            window.find_action,
            window.replace_action,
        ):
            self.assertTrue(action.isEnabled())
        self.assertFalse(window.sync_pdf_action.isEnabled())

        tab = window.current_tab()
        assert tab is not None
        tab.modified = tab.dirty = False
        window.close_tab(0)
        self.assertFalse(window.compile_action.isEnabled())
        self.assertFalse(window.save_action.isEnabled())
        window.close()

    def test_recent_projects_hide_internal_folders_and_remember_real_root(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "paper"
            build_dir = root / ".latex_build"
            history_dir = root / ".icstex" / "history" / "main.tex"
            root.mkdir()
            build_dir.mkdir()
            history_dir.mkdir(parents=True)
            source = root / "main.tex"
            build_file = build_dir / "main.bbl"
            snapshot = history_dir / "snapshot.tex"
            source.write_text("\\documentclass{article}\n\\begin{document}Now\\end{document}\n", encoding="utf-8")
            build_file.write_text("build output", encoding="utf-8")
            snapshot.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            settings = isolated_settings()
            settings.add_recent_project(root)
            settings.add_recent_project(build_dir)
            settings.add_recent_project(history_dir)

            window = MainWindow(settings_store=settings)
            recent_tooltips = {
                button.toolTip()
                for button in window.welcome_page.findChildren(QPushButton)
                if button.objectName() == "welcomeRecent"
            }
            self.assertIn(str(root.resolve()), recent_tooltips)
            self.assertNotIn(str(build_dir.resolve()), recent_tooltips)
            self.assertNotIn(str(history_dir.resolve()), recent_tooltips)

            window._remember_recent_file(build_file)
            self.assertEqual(settings.recent_projects()[0], root.resolve())
            window._remember_recent_file(snapshot)
            self.assertEqual(settings.recent_projects()[0], root.resolve())
            window.close()

    def test_bottom_console_header_stays_available_when_collapsed(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.show()
        app().processEvents()

        self.assertGreater(window.vertical_splitter.sizes()[1], 44)
        window.bottom_collapse_button.click()
        app().processEvents()
        self.assertLessEqual(window.vertical_splitter.sizes()[1], 44)
        self.assertEqual(window.bottom_collapse_button.toolTip(), "展开编译控制台")

        window.bottom_collapse_button.click()
        app().processEvents()
        self.assertGreater(window.vertical_splitter.sizes()[1], 44)
        window.close()

    def test_open_declared_cp1252_preserves_encoding_on_save(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "legacy.tex"
            original = "% !TEX encoding = Windows Latin 1\nRésumé".encode("cp1252")
            source.write_bytes(original)
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)

            with patch.object(window, "compile_current"):
                window.open_file(source)

            tab = window.current_tab()
            self.assertIsNotNone(tab)
            assert tab is not None
            self.assertEqual(tab.encoding, "cp1252")
            self.assertIn("Résumé", tab.editor.toPlainText())
            self.assertIn("编码：cp1252", window.editor_tabs.tabToolTip(0))
            cursor = tab.editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            tab.editor.setTextCursor(cursor)
            tab.editor.insertPlainText("!")
            self.assertTrue(window.save_current())
            self.assertEqual(source.read_bytes(), original + b"!")
            tab.modified = tab.dirty = False
            window.close()

    def test_open_file_never_starts_compile(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("\\documentclass{article}", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())

            with patch.object(window, "compile_current") as compile_current:
                window.open_file(source)

            compile_current.assert_not_called()
            self.assertIn("首次编译", window.statusBar().currentMessage())
            window.close()

    def test_open_invalid_utf8_can_be_cancelled_without_replacement(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "unknown.tex"
            source.write_bytes(b"Paper \x81 text")
            window = MainWindow(settings_store=isolated_settings())

            with patch(
                "app.gui.main_window.QInputDialog.getItem",
                return_value=("简体中文（GB18030）", False),
            ):
                window.open_file(source)

            self.assertEqual(window.editor_tabs.count(), 0)
            self.assertEqual(source.read_bytes(), b"Paper \x81 text")
            window.close()

    def test_open_invalid_utf8_uses_user_selected_encoding(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "legacy.tex"
            source.write_bytes("Résumé".encode("cp1252"))
            window = MainWindow(settings_store=isolated_settings())

            with (
                patch(
                    "app.gui.main_window.QInputDialog.getItem",
                    return_value=("Windows 西文（CP1252）", True),
                ),
                patch.object(window, "compile_current"),
            ):
                window.open_file(source)

            tab = window.current_tab()
            self.assertIsNotNone(tab)
            assert tab is not None
            self.assertEqual(tab.encoding, "cp1252")
            self.assertEqual(tab.editor.toPlainText(), "Résumé")
            tab.modified = tab.dirty = False
            window.close()

    def test_unrepresentable_character_does_not_overwrite_legacy_file(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "legacy.tex"
            original = "% !TEX encoding = Windows Latin 1\nRésumé".encode("cp1252")
            source.write_bytes(original)
            window = MainWindow(settings_store=isolated_settings())
            with patch.object(window, "compile_current"):
                window.open_file(source)
            tab = window.current_tab()
            assert tab is not None
            tab.editor.setPlainText(tab.editor.toPlainText() + "\n中文")

            with patch("app.gui.document_lifecycle.QMessageBox.warning") as warning:
                saved = window.save_current()

            self.assertFalse(saved)
            self.assertEqual(source.read_bytes(), original)
            self.assertIn("cp1252", warning.call_args.args[2])
            tab.modified = tab.dirty = False
            window.close()

    def test_external_encoding_change_preserves_current_editor(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            with patch.object(window, "compile_current"):
                window.open_file(source)
            tab = window.current_tab()
            assert tab is not None
            source.write_bytes(b"Changed \x81")

            with patch.object(window, "_watch_file"):
                window.reload_external_change(str(source))

            self.assertEqual(tab.editor.toPlainText(), "Original")
            self.assertIn("编码与 utf-8 不一致", window.statusBar().currentMessage())
            source.write_text("Original", encoding="utf-8")
            tab.modified = tab.dirty = False
            window.close()

    def test_corrupt_history_snapshot_does_not_replace_editor_text(self) -> None:
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "snapshot.tex"
            snapshot.write_bytes(b"Corrupt \xff")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor("Current paper")
            tab = EditorTab(editor=editor)
            window._add_tab(tab, "main.tex")

            with (
                patch(
                    "app.gui.insertion_actions.QMessageBox.question",
                    return_value=QMessageBox.StandardButton.Yes,
                ),
                patch("app.gui.insertion_actions.QMessageBox.warning") as warning,
            ):
                window.restore_history_snapshot(str(snapshot))

            self.assertEqual(editor.toPlainText(), "Current paper")
            self.assertIn("恢复失败", warning.call_args.args[1])
            tab.modified = tab.dirty = False
            window.close()

    def test_restored_history_marks_existing_pdf_as_stale(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.tex"
            snapshot = root / "snapshot.tex"
            pdf = root / "main.pdf"
            source.write_text("Current paper", encoding="utf-8")
            snapshot.write_text("Older paper", encoding="utf-8")
            pdf.write_bytes(b"%PDF-1.4 current")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor("Current paper")
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            record = window.pdf_state.record_for(source)
            record.last_successful_pdf = pdf
            record.freshness = PdfFreshness.CURRENT
            window._update_pdf_action_state()

            with patch(
                "app.gui.insertion_actions.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                window.restore_history_snapshot(str(snapshot))

            self.assertEqual(editor.toPlainText(), "Older paper")
            self.assertEqual(record.freshness, PdfFreshness.DIRTY)
            self.assertEqual(window.pdf_panel.freshness_label.text(), "源码已修改，PDF 待更新")
            self.assertEqual(editor.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)
            tab.modified = tab.dirty = False
            window.close()

    def test_cancel_keeps_modified_tab_open(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor("Draft")
        tab = EditorTab(editor=editor, modified=True, dirty=True)
        window._add_tab(tab, "未命名.tex")

        with patch(
            "app.gui.editor_tab_manager.QMessageBox.warning",
            return_value=QMessageBox.StandardButton.Cancel,
        ) as warning:
            window.close_tab(0)

        self.assertEqual(window.editor_tabs.count(), 1)
        self.assertIs(window.current_tab(), tab)
        buttons = warning.call_args.args[3]
        self.assertTrue(buttons & QMessageBox.StandardButton.Save)
        self.assertTrue(buttons & QMessageBox.StandardButton.Discard)
        self.assertTrue(buttons & QMessageBox.StandardButton.Cancel)
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_cancel_aborts_window_close_before_cleanup(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor("Draft")
        tab = EditorTab(editor=editor, modified=True, dirty=True)
        window._add_tab(tab, "未命名.tex")
        event = QCloseEvent()

        with (
            patch(
                "app.gui.editor_tab_manager.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.Cancel,
            ),
            patch.object(window.file_watcher, "stop") as stop_watcher,
        ):
            window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        self.assertEqual(window.editor_tabs.count(), 1)
        stop_watcher.assert_not_called()
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_discard_closes_modified_tab_without_saving(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor("Draft")
        tab = EditorTab(editor=editor, modified=True, dirty=True)
        window._add_tab(tab, "未命名.tex")

        with (
            patch(
                "app.gui.editor_tab_manager.QMessageBox.warning",
                return_value=QMessageBox.StandardButton.Discard,
            ),
            patch.object(window, "save_current_as") as save_current_as,
        ):
            window.close_tab(0)

        self.assertEqual(window.editor_tabs.count(), 0)
        save_current_as.assert_not_called()
        window.close()

    def test_late_cancel_keeps_all_tab_managers_running(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        first = EditorTab(
            editor=window._make_editor("First"),
            modified=True,
            dirty=True,
            manager=Mock(root_file=Path("/tmp/first.tex")),
        )
        second = EditorTab(
            editor=window._make_editor("Second"),
            modified=True,
            dirty=True,
            manager=Mock(root_file=Path("/tmp/second.tex")),
        )
        window._add_tab(first, "first.tex")
        window._add_tab(second, "second.tex")
        event = QCloseEvent()

        with patch(
            "app.gui.editor_tab_manager.QMessageBox.warning",
            side_effect=[
                QMessageBox.StandardButton.Discard,
                QMessageBox.StandardButton.Cancel,
            ],
        ):
            window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        self.assertEqual(window.editor_tabs.count(), 2)
        first.manager.stop_current.assert_not_called()
        second.manager.stop_current.assert_not_called()
        first.modified = first.dirty = False
        second.modified = second.dirty = False
        first.manager = second.manager = None
        window.close()

    def test_insert_dialogs_smoke(self) -> None:
        dialogs = [
            FigureDialog(),
            FigureLayoutDialog(),
            TableDialog(),
            HyperlinkDialog(),
            ProjectWizardDialog(),
            BibEntryDialog(),
            BibImportDialog(),
            SettingsDialog(isolated_settings().load_preferences()),
        ]

        for dialog in dialogs:
            self.assertIsNotNone(dialog.windowTitle())
            dialog.close()

    def test_figure_layout_dialog_switches_layout_and_keeps_per_layout_widths(self) -> None:
        dialog = FigureLayoutDialog()

        vertical_index = dialog.layout_combo.findData(FigureLayout.VERTICAL.value)
        dialog.layout_combo.setCurrentIndex(vertical_index)
        self.assertEqual(dialog.values().layout, FigureLayout.VERTICAL)
        self.assertEqual(len(dialog.values().items), 2)
        self.assertEqual([item.width for item in dialog.values().items], [0.8, 0.8])
        self.assertTrue(dialog.item_groups[2].isHidden())

        grid_index = dialog.layout_combo.findData(FigureLayout.GRID_2X2.value)
        dialog.layout_combo.setCurrentIndex(grid_index)
        for index, edit in enumerate(dialog.image_edits):
            edit.setText(f"/tmp/{index}.png")
        for spin, width in zip(dialog.width_spins, (0.55, 0.40, 0.45, 0.50), strict=True):
            spin.setValue(width)
        values = dialog.values()

        self.assertEqual(values.layout, FigureLayout.GRID_2X2)
        self.assertEqual(len(values.items), 4)
        self.assertEqual([item.width for item in values.items], [0.55, 0.40, 0.45, 0.50])
        self.assertFalse(dialog.item_groups[3].isHidden())
        self.assertIn("上排 0.95", dialog.layout_hint.text())
        self.assertIn("不会拉伸变形", dialog.layout_hint.text())
        self.assertGreaterEqual(
            dialog.minimumWidth(),
            dialog.item_container.sizeHint().width() + 48,
        )
        self.assertLessEqual(dialog.item_scroll.height(), 300)
        dialog.close()

    def test_normal_mode_inserts_adjustable_grid_figure_layout(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.tex"
            source.write_text(
                "\\documentclass{article}\n\\begin{document}\n\\end{document}\n",
                encoding="utf-8",
            )
            image_paths = []
            for name in ("a.png", "b.png", "c.png", "d.png"):
                image = root / name
                image.write_bytes(b"image")
                image_paths.append(image)

            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            dialog = Mock()
            dialog.exec.return_value = QDialog.DialogCode.Accepted
            dialog.values.return_value = FigureLayoutSpec(
                layout=FigureLayout.GRID_2X2,
                items=tuple(
                    FigureLayoutItem(str(path), width, path.stem.upper())
                    for path, width in zip(
                        image_paths,
                        (0.55, 0.40, 0.45, 0.50),
                        strict=True,
                    )
                ),
                caption="Four panels",
                label="fig:grid",
            )

            with patch("app.gui.insertion_actions.FigureLayoutDialog", return_value=dialog):
                window.insert_side_by_side_figures()

            text = editor.toPlainText()
            self.assertEqual(text.count("\\begin{subfigure}"), 4)
            self.assertIn("\\begin{subfigure}{0.55\\textwidth}", text)
            self.assertIn("\\begin{subfigure}{0.4\\textwidth}", text)
            self.assertEqual(text.count("\\hfill"), 2)
            self.assertIn("\\par\\medskip", text)
            self.assertIn("\\usepackage{subcaption}", text)
            self.assertIn("\\label{fig:grid}", text)
            for image in image_paths:
                self.assertTrue((root / "figures" / image.name).is_file())
            tab.modified = tab.dirty = False
            window.close()

    def test_layout_asset_copy_rolls_back_partial_failure(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.tex"
            source.write_text("", encoding="utf-8")
            first = root / "first.png"
            second = root / "second.png"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            window = MainWindow(settings_store=isolated_settings())
            tab = EditorTab(editor=window._make_editor(""), path=source)

            def copy_then_fail(source_path: Path, destination: Path) -> None:
                if source_path == second:
                    raise OSError("simulated copy failure")
                destination.write_bytes(source_path.read_bytes())

            with (
                patch("app.gui.insertion_actions.copy_image_atomic", side_effect=copy_then_fail),
                patch("app.gui.insertion_actions.QMessageBox.warning") as warning,
            ):
                result = window.insertions.copy_image_assets(tab, [str(first), str(second)])

            self.assertIsNone(result)
            self.assertEqual(list((root / "figures").glob("*")), [])
            self.assertIn("已回滚新增图片", warning.call_args.args[2])
            window.close()

    def test_environment_doctor_dialog_smoke(self) -> None:
        from app.core.environment_doctor import build_environment_report

        report = build_environment_report(LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None))
        dialog = EnvironmentDoctorDialog(report)

        self.assertIn("环境诊断报告", dialog.report_view.toPlainText())
        dialog.close()

    def test_environment_doctor_dialog_copies_feedback_bundle(self) -> None:
        from app.core.environment_doctor import build_environment_report
        from app.gui.environment_doctor_dialog import FeedbackContext

        report = build_environment_report(LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None))
        provider = lambda: FeedbackContext(recent_log="compile log tail line", project_file="thesis.tex")
        dialog = EnvironmentDoctorDialog(report, feedback_context_provider=provider)

        dialog.feedback_button.click()

        clipboard_text = QApplication.clipboard().text()
        self.assertIn("反馈包", clipboard_text)
        self.assertIn("thesis.tex", clipboard_text)
        self.assertIn("compile log tail line", clipboard_text)
        self.assertEqual(dialog.feedback_button.text(), "已复制反馈包")
        dialog.close()

    def test_direct_feedback_action_copies_privacy_safe_bundle(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "SecretProject" / "main.tex"
            source.parent.mkdir()
            source.write_text("\\documentclass{article}\nPrivate paper text", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            window.log_view.setPlainText(
                f"Running: latexmk {source}\n"
                "l.42 Private paper text echoed by TeX"
            )

            window.feedback_bundle_action.trigger()

            bundle = QApplication.clipboard().text()
            self.assertIn("ICSTeX 反馈包", bundle)
            self.assertIn("main.tex", bundle)
            self.assertNotIn("SecretProject", bundle)
            self.assertNotIn("Private paper text", bundle)
            self.assertNotIn("Running: latexmk", bundle)
            self.assertIsNone(window._build_feedback_context(include_recent_log=False).recent_log)
            self.assertIn("原始编译日志", window.statusBar().currentMessage())
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_table_dialog_values_include_grid_content(self) -> None:
        dialog = TableDialog()
        dialog.preview_table.item(0, 0).setText("Mass")
        dialog.preview_table.item(0, 1).setText("Time")
        dialog.preview_table.item(1, 0).setText("1 kg")
        dialog.preview_table.item(1, 1).setText("2 s")

        values = dialog.values()

        self.assertEqual(values.headers[:2], ("Mass", "Time"))
        self.assertEqual(values.cells[0][:2], ("1 kg", "2 s"))
        dialog.close()

    def test_table_dialog_load_spec_fills_grid(self) -> None:
        from app.core.latex_insertions import parse_tabular, table_snippet

        spec = parse_tabular(
            table_snippet(
                replace(
                    TableDialog().values(),
                    rows=1,
                    columns=2,
                    headers=("Mass", "Time"),
                    cells=(("1 kg", "2 s"),),
                )
            )
        )
        dialog = TableDialog()
        dialog.load_spec(spec)

        self.assertEqual(dialog.columns_spin.value(), 2)
        self.assertEqual(dialog._cell_text(0, 0), "Mass")
        self.assertEqual(dialog._cell_text(1, 1), "2 s")
        dialog.close()

    def test_table_dialog_load_spec_from_delimited_paste(self) -> None:
        from app.core.latex_insertions import parse_delimited

        dialog = TableDialog()
        dialog.load_spec(parse_delimited("Name\tScore\nAlice\t90"))

        self.assertEqual(dialog.columns_spin.value(), 2)
        self.assertEqual(dialog._cell_text(0, 1), "Score")
        self.assertEqual(dialog._cell_text(1, 0), "Alice")
        dialog.close()

    def test_bib_import_dialog_online_checkbox_defaults_off(self) -> None:
        dialog = BibImportDialog()

        self.assertFalse(dialog.online())
        dialog.online_check.setChecked(True)
        self.assertTrue(dialog.online())
        dialog.close()

    def test_engine_selector_updates_current_engine(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        index = window.engine_selector.findData(LaTeXEngine.XELATEX.value)
        window.engine_selector.setCurrentIndex(index)

        self.assertEqual(window.current_engine, LaTeXEngine.XELATEX)
        self.assertTrue(window.engine_actions[LaTeXEngine.XELATEX].isChecked())
        window.close()

    def test_editor_soft_wrap_is_enabled_by_default(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        editor = window._make_editor("A very long line " * 40)

        self.assertTrue(editor.soft_wrap_enabled)
        self.assertEqual(editor.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)
        window.close()

    def test_soft_wrap_preference_applies_to_open_editors(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        editor = window._make_editor("A very long line " * 40)
        tab = EditorTab(editor=editor)
        window._add_tab(tab, "Untitled.tex")

        window.apply_preferences(replace(window.preferences, soft_wrap=False))

        self.assertFalse(editor.soft_wrap_enabled)
        self.assertEqual(editor.lineWrapMode(), QPlainTextEdit.LineWrapMode.NoWrap)
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_generated_table_and_hyperlink_preserve_soft_wrap(self) -> None:
        from app.core.latex_insertions import (
            HYPERLINK_PACKAGES,
            TABLE_PACKAGES,
            HyperlinkSpec,
            TableSpec,
            hyperlink_snippet,
            table_snippet,
        )

        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor("\\documentclass{article}\n\\begin{document}\n\n\\end{document}\n")
        tab = EditorTab(editor=editor)
        window._add_tab(tab, "Untitled.tex")

        long_url = "https://example.com/" + "verylongsegment" * 40
        table = TableSpec(
            rows=2,
            columns=8,
            headers=tuple(f"VeryLongHeaderName{index}" for index in range(8)),
        )
        window.insertions.insert_snippet(
            tab,
            hyperlink_snippet(HyperlinkSpec(text="Long link", url=long_url)),
            HYPERLINK_PACKAGES,
            "link",
            block=False,
        )
        window.insertions.insert_snippet(tab, table_snippet(table), TABLE_PACKAGES, "table")

        QApplication.processEvents()
        self.assertTrue(editor.soft_wrap_enabled)
        self.assertEqual(editor.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.assertEqual(editor.horizontalScrollBar().maximum(), 0)
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_compile_manager_honors_magic_root_and_program_in_auto_mode(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "main.tex"
            chapter = root / "chapter.tex"
            main.write_text("\\documentclass{article}\n\\begin{document}\n\\input{chapter}\n\\end{document}", encoding="utf-8")
            chapter.write_text("% !TEX root = main.tex\n% !TEX program = xelatex\nText", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.current_engine = LaTeXEngine.AUTO

            manager = window.compile.create_manager(chapter)

            self.assertEqual(manager.root_file, main.resolve())
            self.assertEqual(manager.engine, LaTeXEngine.XELATEX)
            window.close()

    def test_manual_engine_selection_overrides_magic_program(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("% !TEX program = xelatex\n\\documentclass{article}", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.current_engine = LaTeXEngine.PDFLATEX

            manager = window.compile.create_manager(source)

            self.assertEqual(manager.engine, LaTeXEngine.PDFLATEX)
            window.close()

    def test_startup_without_latex_does_not_show_modal_warning(self) -> None:
        missing_toolchain = LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None)
        with patch("app.gui.main_window.detect_toolchain", return_value=missing_toolchain), patch.object(QMessageBox, "warning") as warning:
            window = MainWindow(settings_store=isolated_settings())

        warning.assert_not_called()
        self.assertIn("LaTeX 环境未就绪", window.statusBar().currentMessage())
        window.close()

    def test_compile_without_latex_warns_only_when_user_triggers_compile(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("\\begin{document}Hello\\end{document}", encoding="utf-8")
            missing_toolchain = LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None)
            window = MainWindow(settings_store=isolated_settings())
            window.toolchain = missing_toolchain
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            with patch.object(QMessageBox, "warning") as warning:
                window.compile_current(immediate=True)
                warning.assert_not_called()
                window.compile_current(immediate=True, show_missing_warning=True)

            warning.assert_called_once()
            window.close()

    def test_auto_compile_off_editor_change_does_not_schedule_compile(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            with patch.object(window, "schedule_save") as schedule_save:
                editor.setPlainText("Changed")

            self.assertTrue(tab.modified)
            self.assertTrue(tab.dirty)
            schedule_save.assert_called_once()
            self.assertFalse(schedule_save.call_args.kwargs["compile_after_save"])
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_auto_compile_on_editor_change_schedules_compile_after_save(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(True)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            with patch.object(window, "schedule_save") as schedule_save:
                editor.setPlainText("Changed")

            self.assertTrue(tab.modified)
            self.assertTrue(tab.dirty)
            schedule_save.assert_called_once()
            self.assertTrue(schedule_save.call_args.kwargs["compile_after_save"])
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_editor_change_waits_for_flush_before_saving(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            editor.setPlainText("Changed")

            self.assertEqual(source.read_text(encoding="utf-8"), "Original")
            self.assertTrue(tab.modified)
            self.assertTrue(tab.dirty)
            self.assertIsNotNone(tab.save_timer)
            self.assertTrue(tab.save_timer.isActive())

            self.assertTrue(window.flush_pending_save(tab))
            self.assertEqual(source.read_text(encoding="utf-8"), "Changed")
            self.assertFalse(tab.modified)
            self.assertFalse(tab.dirty)
            window.close()

    def test_external_save_echo_does_not_reload_or_jump_to_top(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            text = "\n".join(f"Line {index}" for index in range(80))
            source.write_text(text, encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(text)
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            cursor = editor.textCursor()
            cursor.setPosition(len(text))
            editor.setTextCursor(cursor)

            with patch.object(window, "compile_current") as compile_current:
                window.reload_external_change(str(source))

            self.assertEqual(editor.textCursor().position(), len(text))
            compile_current.assert_not_called()
            window.close()

    def test_external_reload_preserves_cursor_position(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            text = "\n".join(f"Line {index}" for index in range(80))
            updated = text.replace("Line 20", "Changed 20")
            source.write_text(text, encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(text)
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            cursor = editor.textCursor()
            cursor.setPosition(len(text))
            editor.setTextCursor(cursor)
            source.write_text(updated, encoding="utf-8")

            with patch.object(window, "compile_current") as compile_current:
                window.reload_external_change(str(source))

            self.assertEqual(editor.toPlainText(), updated)
            self.assertEqual(editor.textCursor().position(), min(len(text), len(updated)))
            compile_current.assert_called_once()
            window.close()

    def test_external_edit_racing_own_save_is_not_silently_dropped(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            original = "Original"
            source.write_text(original, encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(original)
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            self.assertTrue(window._save_tab(tab, source))

            # A real external edit lands on disk within the same save-echo
            # window. It must not be silently discarded just because it is
            # close in time to our own save.
            raced_content = "Raced external edit"
            source.write_text(raced_content, encoding="utf-8")

            assert tab.manager is not None
            window.compile_authorized_roots.add(tab.manager.root_file)
            with patch.object(tab.manager, "schedule_compile") as schedule_compile:
                window.reload_external_change(str(source))

            self.assertEqual(editor.toPlainText(), raced_content)
            schedule_compile.assert_called_once()
            window.close()

    def test_finished_compile_for_inactive_tab_does_not_override_pdf(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            tex_a = root / "a.tex"
            tex_b = root / "b.tex"
            tex_a.write_text("A", encoding="utf-8")
            tex_b.write_text("B", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window._watch_file = lambda _path: None  # type: ignore[method-assign]

            tab_a = EditorTab(editor=window._make_editor("A"), path=tex_a)
            window._add_tab(tab_a, tex_a.name)
            tab_a.manager = window.create_compile_manager(tex_a)

            tab_b = EditorTab(editor=window._make_editor("B"), path=tex_b)
            window._add_tab(tab_b, tex_b.name)  # becomes the active tab

            self.assertIs(window.current_tab(), tab_b)

            tab_a.manager.output_dir.mkdir(parents=True, exist_ok=True)
            tab_a.manager.pdf_file.write_bytes(b"%PDF-1.4 A")
            stale_result = CompileResult(
                root_file=tab_a.manager.root_file,
                output_dir=tab_a.manager.output_dir,
                pdf_file=tab_a.manager.pdf_file,
                log_file=tab_a.manager.log_file,
                command=[],
                returncode=0,
                stdout="",
                stderr="",
                duration_seconds=0.1,
                outcome=CompileOutcome.SUCCESS,
                errors=[],
                build_id=1,
            )

            with patch.object(window.pdf_panel, "load_pdf") as load_pdf:
                window.compile.on_finished(stale_result)

            load_pdf.assert_not_called()
            # B has no successful PDF of its own; A's result must not enable export.
            self.assertFalse(window.export_pdf_action.isEnabled())
            window.close()

    def test_compile_current_refreshes_engine_from_magic_comment(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            original = "\\documentclass{article}\n\\begin{document}\nA\n\\end{document}\n"
            source.write_text(original, encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.toolchain = LaTeXToolchain(
                latexmk="/bin/latexmk", pdflatex="/bin/pdflatex", texcount=None, synctex=None
            )
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(original)
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)
            tab.manager = window.create_compile_manager(source)
            self.assertEqual(tab.manager.engine, LaTeXEngine.AUTO)

            # User adds a "% !TEX program" comment to an already-open
            # document and saves; this should pick a different engine the
            # very next time it compiles, without needing to reopen the file.
            updated = "% !TEX program = xelatex\n" + original
            editor.setPlainText(updated)

            with patch.object(tab.manager, "schedule_compile") as schedule_compile:
                window.compile_current()

            self.assertEqual(tab.manager.engine, LaTeXEngine.XELATEX)
            schedule_compile.assert_called_once()
            window.close()

    def test_enter_continues_item(self) -> None:
        editor = LaTeXEditor("\\begin{itemize}\n  \\item One")
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)

        editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "\r"))

        self.assertTrue(editor.toPlainText().endswith("\\item One\n  \\item "))

    def test_environment_completion_after_closing_brace(self) -> None:
        editor = LaTeXEditor("\\begin{equation")
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)

        editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_BraceRight, Qt.KeyboardModifier.NoModifier, "}"))

        self.assertEqual(editor.toPlainText(), "\\begin{equation}\n  \n\\end{equation}")

    def test_completion_enter_uses_popup_highlighted_row(self) -> None:
        editor = LaTeXEditor(r"\text")
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)
        editor.show()
        editor._show_completion_if_available()
        app().processEvents()

        popup = editor._completer.popup()
        completion_model = editor._completer.completionModel()
        popup.setCurrentIndex(completion_model.index(1, 0))
        self.assertEqual(popup.currentIndex().data(), r"\textit{}")
        self.assertEqual(editor._completer.currentCompletion(), r"\textbf{}")

        editor.keyPressEvent(
            QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Return,
                Qt.KeyboardModifier.NoModifier,
                "\r",
            )
        )

        self.assertEqual(editor.toPlainText(), r"\textit{}")
        editor.close()

    def test_tab_expands_snippet(self) -> None:
        editor = LaTeXEditor("fig")
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)

        editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier, "\t"))

        self.assertIn("\\begin{figure}", editor.toPlainText())
        self.assertIn("\\includegraphics", editor.toPlainText())

    def test_insert_latex_snippet_moves_cursor(self) -> None:
        editor = LaTeXEditor("Hello")

        editor.insert_latex_snippet("\\begin{equation}\n  \n\\end{equation}", len("\\begin{equation}\n  "))

        self.assertIn("\\end{equation}", editor.toPlainText())
        self.assertEqual(editor.textCursor().position(), len("\\begin{equation}\n  "))

    def test_editor_drop_emits_image_paths_only_for_images(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "plot.png"
            text_file = root / "notes.txt"
            image.write_bytes(b"image")
            text_file.write_text("notes", encoding="utf-8")
            editor = LaTeXEditor()
            received: list[str] = []
            editor.imageDropped.connect(lambda paths: received.extend(paths))

            image_mime = QMimeData()
            image_mime.setUrls([QUrl.fromLocalFile(str(image))])
            image_event = QDropEvent(
                QPointF(1, 1),
                Qt.DropAction.CopyAction,
                image_mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            editor.dropEvent(image_event)

            text_mime = QMimeData()
            text_mime.setUrls([QUrl.fromLocalFile(str(text_file))])
            text_event = QDropEvent(
                QPointF(1, 1),
                Qt.DropAction.CopyAction,
                text_mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
            editor.dropEvent(text_event)

        self.assertEqual(received, [str(image)])

    def test_generated_snippet_inserts_package_and_text(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        window.new_document()
        tab = window.current_tab()
        assert tab is not None

        window._insert_generated_snippet(
            tab,
            "\\href{https://example.com}{Example}",
            HYPERLINK_PACKAGES,
            "已插入超链接。",
            block=False,
        )

        text = tab.editor.toPlainText()
        self.assertIn("\\usepackage{hyperref}", text)
        self.assertIn("\\href{https://example.com}{Example}", text)
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_dropped_image_inserts_figure_and_copies_asset(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.tex"
            image = root / "raw image.png"
            source.write_text("\\documentclass{article}\n\\begin{document}\n\\end{document}\n", encoding="utf-8")
            image.write_bytes(b"image")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            window.insert_dropped_images([str(image)])
            self.assertTrue(
                wait_until(lambda: "\\includegraphics" in editor.toPlainText()),
                "drop import did not complete",
            )

            text = editor.toPlainText()
            # Already inside the project: reused without creating a copy.
            self.assertFalse((root / "figures").exists())
            self.assertIn("\\usepackage{graphicx}", text)
            self.assertIn("\\includegraphics[width=0.8\\textwidth]{raw image.png}", text)
            self.assertIn("\\caption{raw image}", text)
            self.assertIn("\\label{fig:raw_image}", text)
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_dropped_external_image_is_copied_into_figures(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            outside = Path(directory).parent / "external-source"
            outside.mkdir(exist_ok=True)
            image = outside / "plot.png"
            image.write_bytes(b"image")
            source = root / "main.tex"
            source.write_text("\\documentclass{article}\n\\begin{document}\n\\end{document}\n", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            window.insert_dropped_images([str(image)])
            self.assertTrue(
                wait_until(lambda: "\\includegraphics" in editor.toPlainText()),
                "drop import did not complete",
            )

            self.assertTrue((root / "figures" / "plot.png").exists())
            self.assertIn("{figures/plot.png}", editor.toPlainText())
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_dropped_images_insert_multiple_figures(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.tex"
            first = root / "first.png"
            second = root / "second.jpg"
            source.write_text("\\documentclass{article}\n\\begin{document}\n\\end{document}\n", encoding="utf-8")
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            window.insert_dropped_images([str(first), str(second)])
            self.assertTrue(
                wait_until(lambda: editor.toPlainText().count("\\begin{figure}") == 2),
                "drop import did not complete",
            )

            text = editor.toPlainText()
            self.assertEqual(text.count("\\begin{figure}"), 2)
            self.assertIn("{first.png}", text)
            self.assertIn("{second.jpg}", text)
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_dropped_images_roll_back_on_failure(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            outside = Path(directory).parent / "external-fail-source"
            outside.mkdir(exist_ok=True)
            good = outside / "good.png"
            good.write_bytes(b"good")
            missing = outside / "missing.png"
            source = root / "main.tex"
            source.write_text("\\documentclass{article}\n\\begin{document}\n\\end{document}\n", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            with patch("app.gui.insertion_actions.QMessageBox.warning") as warning:
                window.insert_dropped_images([str(good), str(missing)])
                self.assertTrue(
                    wait_until(lambda: warning.called),
                    "failure warning did not appear",
                )

            self.assertNotIn("\\begin{figure}", editor.toPlainText())
            self.assertFalse((root / "figures" / "good.png").exists())
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_dropped_image_requires_saved_document(self) -> None:
        with TemporaryDirectory() as directory:
            image = Path(directory) / "plot.png"
            image.write_bytes(b"image")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor("\\documentclass{article}\n\\begin{document}\n\\end{document}\n")
            tab = EditorTab(editor=editor)
            window._add_tab(tab, "Untitled.tex")

            with patch.object(QMessageBox, "information") as information:
                window.insert_dropped_images([str(image)])

            information.assert_called_once()
            self.assertNotIn("\\includegraphics", editor.toPlainText())
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_word_count_refresh_reads_unsaved_editor_text(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.toolchain = LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None)
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor("\\begin{document}Hello 42 world.\\end{document}")
        tab = EditorTab(editor=editor)
        window._add_tab(tab, "Untitled.tex")

        window.update_word_count()

        self.assertEqual(window.word_count_labels["effective"].text(), "2")
        self.assertEqual(window.word_count_labels["numbers"].text(), "1")
        self.assertIn("ICSTeX 结构化统计", window.word_count_meta.text())
        self.assertIn("未找到 TeXcount", window.word_count_meta.text())
        self.assertIn("当前编辑器内容", window.word_count_meta.text())
        self.assertEqual(window.word_count_view.last_mode_label, "ICSTeX 结构化统计")
        window.close()

    def test_word_count_uses_project_root_and_unsaved_child_buffer(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "main.tex"
            child = Path(directory) / "child.tex"
            root.write_text(
                "\\documentclass{article}\n\\begin{document}Root.\\input{child}\\end{document}",
                encoding="utf-8",
            )
            child.write_text("Old disk text.", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.toolchain = LaTeXToolchain(latexmk=None, pdflatex=None, texcount=None, synctex=None)
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor("Unsaved child buffer has five words.")
            tab = EditorTab(editor=editor, path=child, modified=True, dirty=True)
            window._add_tab(tab, child.name)

            window.update_word_count()

            self.assertEqual(window.word_count_labels["effective"].text(), "7")
            preview = window.word_count_view.preview_browser.toPlainText()
            self.assertIn("main.tex", preview)
            self.assertIn("child.tex", preview)
            self.assertIn("Unsaved child buffer has five words", preview)
            self.assertNotIn("Old disk text", preview)
            self.assertEqual(child.read_text(encoding="utf-8"), "Old disk text.")
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_feedback_context_includes_non_private_debug_metadata(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "main.tex"
            chapter = root / "chapter.tex"
            main.write_text("\\documentclass{article}\n\\begin{document}\n\\input{chapter}\n\\end{document}", encoding="utf-8")
            chapter.write_text("% !TEX root = main.tex\nBody", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.current_engine = LaTeXEngine.XELATEX
            editor = window._make_editor(chapter.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=chapter)
            window._add_tab(tab, chapter.name)
            # Set after _add_tab: tab activation now syncs the timer label to
            # the active root's record.
            window.compile_time_label.setText("上次编译 7.25s")
            window.word_count_view.last_mode_label = "TeXcount 兼容统计"

            context = window._build_feedback_context()

            self.assertEqual(context.project_file, chapter)
            self.assertIsNotNone(context.metadata)
            assert context.metadata is not None
            self.assertEqual(Path(str(context.metadata.root_file)).name, "main.tex")
            self.assertEqual(context.metadata.root_source, "magic comment")
            self.assertEqual(context.metadata.selected_engine, "XeLaTeX")
            self.assertEqual(context.metadata.latest_compile_seconds, 7.25)
            self.assertEqual(context.metadata.word_count_mode, "TeXcount 兼容统计")
            window.close()

    def test_refresh_project_panels_reads_labels_and_bib_keys(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bib").mkdir()
            source = root / "main.tex"
            source.write_text(
                "\\documentclass{article}\n\\begin{document}\n\\section{Intro}\n\\label{sec:intro}\\cite{Storm2024}\n\\end{document}\n",
                encoding="utf-8",
            )
            (root / "bib" / "references.bib").write_text("@article{Storm2024,\n  title = {Weather}\n}\n", encoding="utf-8")
            (root / "figures").mkdir()
            (root / "figures" / "plot.png").write_text("", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            window.refresh_project_panels()

            self.assertEqual(window.labels_panel.table.item(0, 0).text(), "sec:intro")
            self.assertEqual(window.references_panel.table.item(0, 0).text(), "Storm2024")
            self.assertEqual(window.outline_panel.table.item(0, 0).text(), "Intro")
            self.assertEqual(window.images_panel.table.item(0, 0).text(), "plot.png")
            self.assertEqual(editor._completion_labels, ["sec:intro"])
            self.assertEqual(editor._completion_citations, ["Storm2024"])
            window.close()

    def test_clean_build_cache_removes_current_build_dir(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            build_dir = source.parent / ".latex_build"
            build_dir.mkdir()
            (build_dir / "main.aux").write_text("", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            self.assertTrue(window.clean_build_cache())

            self.assertFalse(build_dir.exists())
            window.close()

    def test_clean_build_cache_refuses_while_worker_has_not_stopped(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("x", encoding="utf-8")
            window = MainWindow(settings_store=isolated_settings())
            window._watch_file = lambda _path: None  # type: ignore[method-assign]
            tab = EditorTab(editor=window._make_editor("x"), path=source)
            window._add_tab(tab, source.name)
            tab.manager = window.create_compile_manager(source)
            build_dir = tab.manager.output_dir
            build_dir.mkdir(parents=True)
            marker = build_dir / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            tab.manager._idle_event.clear()

            try:
                with patch.object(tab.manager, "stop_current", return_value=False), patch(
                    "app.gui.compile_controller.QMessageBox.warning"
                ) as warning, patch("app.gui.compile_controller.shutil.rmtree") as rmtree:
                    self.assertFalse(window.clean_build_cache())

                warning.assert_called_once()
                rmtree.assert_not_called()
                self.assertTrue(marker.exists())
            finally:
                tab.manager._idle_event.set()
                tab.modified = False
                tab.dirty = False
                window.close()

    def test_welcome_page_hides_when_document_opens_and_returns_when_closed(self) -> None:
        window = MainWindow(settings_store=isolated_settings())

        self.assertEqual(window.source_stack.currentWidget(), window.welcome_page)

        window.new_document()
        self.assertEqual(window.source_stack.currentWidget(), window.editor_tabs)

        tab = window.current_tab()
        assert tab is not None
        tab.modified = False
        tab.dirty = False
        window.close_tab(0)

        self.assertEqual(window.source_stack.currentWidget(), window.welcome_page)
        window.close()

    def test_project_check_and_fix_insert_missing_package(self) -> None:
        window = MainWindow(settings_store=isolated_settings())
        window.toolchain = LaTeXToolchain(latexmk="/bin/latexmk", pdflatex="/bin/pdflatex", texcount=None, synctex=None)
        editor = window._make_editor(
            "\\documentclass{article}\n\\begin{document}\n\\includegraphics{figures/a.png}\n\\end{document}\n"
        )
        tab = EditorTab(editor=editor)
        window._add_tab(tab, "Untitled.tex")

        diagnostics = window.run_project_check(switch_to_panel=False)
        fix_index = next(index for index, diagnostic in enumerate(diagnostics) if diagnostic.fix is not None)
        window.fix_diagnostic(fix_index)

        self.assertIn("\\usepackage{graphicx}", editor.toPlainText())
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_log_bridge_install_and_uninstall(self) -> None:
        import logging
        from app.gui.log_bridge import QtLogBridge

        bridge = QtLogBridge()
        logger_name = "icstex.test.log_bridge_smoke"
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()

        bridge.install_on(logger_name, level=logging.DEBUG)
        self.assertIn(bridge.handler, logger.handlers)
        self.assertLessEqual(logger.level, logging.DEBUG)

        received: list[str] = []
        bridge.messageEmitted.connect(lambda _name, _level, msg: received.append(msg))
        logger.info("hello from log bridge")
        QApplication.processEvents()
        self.assertTrue(any("hello from log bridge" in m for m in received))

        bridge.uninstall()
        self.assertNotIn(bridge.handler, logger.handlers)
        self.assertEqual(bridge._installed_loggers, [])


class GuiPdfStateTests(TestCase):
    """Root-scoped PDF freshness scenarios from the state-machine assignment."""

    def setUp(self) -> None:
        app()
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.window = MainWindow(settings_store=isolated_settings())
        self.window._watch_file = lambda _path: None  # type: ignore[method-assign]
        self.window.auto_compile_action.setChecked(False)
        self.addCleanup(self._close_window)

    def _close_window(self) -> None:
        for tab in self.window.tabs.values():
            tab.modified = False
            tab.dirty = False
        self.window.close()

    def _add_doc(self, name: str, text: str = "hello") -> EditorTab:
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        tab = EditorTab(editor=self.window._make_editor(text), path=path)
        self.window._add_tab(tab, path.name)
        tab.manager = self.window.create_compile_manager(path)
        return tab

    def _result(
        self,
        manager: CompileManager,
        outcome: CompileOutcome,
        build_id: int,
        *,
        returncode: int = 0,
        errors: list[LaTeXError] | None = None,
        stderr: str = "",
        purpose: BuildPurpose = BuildPurpose.FINAL,
        preview_asset_paths: tuple[Path, ...] = (),
    ) -> CompileResult:
        return CompileResult(
            root_file=manager.root_file,
            output_dir=manager.output_dir_for(purpose),
            pdf_file=manager.pdf_file_for(purpose),
            log_file=manager.log_file_for(purpose),
            command=[],
            returncode=returncode,
            stdout="",
            stderr=stderr,
            duration_seconds=0.1,
            outcome=outcome,
            errors=errors or [],
            build_id=build_id,
            purpose=purpose,
            preview_fidelity="proxy" if purpose is BuildPurpose.PREVIEW else None,
            preview_manifest_digest="digest" if purpose is BuildPurpose.PREVIEW else None,
            preview_asset_paths=preview_asset_paths,
        )

    def _begin_preview_owned_by(self, manager: CompileManager, build_id: int) -> None:
        with manager._lock:
            manager._active_purpose = BuildPurpose.PREVIEW
        self.window.compile._emit_started(manager, manager.root_file, build_id)

    def _late_preview_result(
        self,
        manager: CompileManager,
        build_id: int,
        asset: Path,
    ) -> CompileResult:
        pdf = manager.pdf_file_for(BuildPurpose.PREVIEW)
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(b"%PDF-1.4 late")
        return self._result(
            manager,
            CompileOutcome.SUCCESS,
            build_id,
            purpose=BuildPurpose.PREVIEW,
            preview_asset_paths=(asset,),
        )

    def _finish_success(self, tab: EditorTab, build_id: int, pdf_bytes: bytes = b"%PDF-1.4 x") -> Path:
        manager = tab.manager
        assert manager is not None
        manager.output_dir.mkdir(parents=True, exist_ok=True)
        manager.pdf_file.write_bytes(pdf_bytes)
        self.window.compile._emit_started(manager, manager.root_file, build_id)
        self.window.compile.on_finished(self._result(manager, CompileOutcome.SUCCESS, build_id))
        return manager.pdf_file

    def _banner(self) -> str:
        return self.window.pdf_panel.freshness_label.text()

    def test_closed_manager_late_signals_cannot_restore_state_or_watchers(self) -> None:
        tab = self._add_doc("close.tex")
        manager = tab.manager
        assert manager is not None
        asset = self.dir / "close.png"
        asset.write_bytes(b"image")
        self._begin_preview_owned_by(manager, 101)
        result = self._late_preview_result(manager, 101, asset)

        index = self.window._index_for_tab_id(id(tab.editor))
        self.window.close_tab(index)
        self.window.compile._emit_started(manager, manager.root_file, 102)
        self.window.compile.on_finished(result)

        self.assertNotIn(manager.root_file, self.window.compile_managers)
        self.assertNotIn(asset.resolve(), self.window.preview_asset_roots)
        self.assertFalse(self.window.preview_state.record_for(manager.root_file).has_valid_pdf)

    def test_save_as_manager_late_signals_cannot_restore_old_root(self) -> None:
        tab = self._add_doc("old.tex")
        manager = tab.manager
        assert manager is not None
        asset = self.dir / "old.png"
        asset.write_bytes(b"image")
        self._begin_preview_owned_by(manager, 111)
        result = self._late_preview_result(manager, 111, asset)

        new_path = self.dir / "new.tex"
        self.assertTrue(self.window.documents.save_tab(tab, new_path))
        self.window.compile._emit_started(manager, manager.root_file, 112)
        self.window.compile.on_finished(result)

        self.assertIsNot(tab.manager, manager)
        self.assertNotIn(manager.root_file, self.window.compile_managers)
        self.assertNotIn(asset.resolve(), self.window.preview_asset_roots)
        self.assertFalse(self.window.preview_state.record_for(manager.root_file).has_valid_pdf)

    def test_rebuilt_manager_late_signals_cannot_mutate_new_owner(self) -> None:
        tab = self._add_doc("rebuild.tex")
        manager = tab.manager
        assert manager is not None
        asset = self.dir / "rebuild.png"
        asset.write_bytes(b"image")
        self._begin_preview_owned_by(manager, 121)
        result = self._late_preview_result(manager, 121, asset)
        queued_key = (manager.root_file, 122)
        self.window.compile_build_owners[queued_key] = manager
        self.window.compile_purposes[queued_key] = BuildPurpose.PREVIEW

        self.window.compile.rebuild_managers()
        replacement = tab.manager
        assert replacement is not None
        # Simulate a started signal that was emitted before retirement but was
        # still queued in Qt until after the same-root replacement was created.
        self.window.compile.on_started(str(manager.root_file), 122)
        self.window.compile.on_finished(result)

        self.assertIsNot(replacement, manager)
        self.assertIs(self.window.compile_managers[manager.root_file], replacement)
        self.assertNotIn(asset.resolve(), self.window.preview_asset_roots)
        self.assertFalse(self.window.preview_state.record_for(manager.root_file).has_valid_pdf)
        self.assertIsNot(
            self.window.preview_state.record_for(manager.root_file).freshness,
            PreviewFreshness.COMPILING,
        )
        self.assertNotIn(manager.root_file, self.window.compile_active_builds)
        self.assertNotIn(manager.root_file, self.window.compile_start_times)
        self.assertFalse(self.window.stop_compile_action.isEnabled())
        self.assertFalse(self.window.compile_progress.isVisible())

    def test_success_then_edit_keeps_pdf_and_shows_dirty(self) -> None:
        tab = self._add_doc("a.tex")
        pdf = self._finish_success(tab, 1)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        self.assertEqual(self._banner(), "PDF 已是最新")
        self.assertTrue(self.window.export_pdf_action.isEnabled())

        tab.editor.insertPlainText("more text")

        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        self.assertEqual(self._banner(), "源码已修改，PDF 待更新")
        self.assertTrue(self.window.export_pdf_action.isEnabled())

    def test_new_revision_reloads_same_pdf_path_with_root_logical_key(self) -> None:
        tab = self._add_doc("a.tex")
        pdf = self._finish_success(tab, 1)
        manager = tab.manager
        assert manager is not None

        tab.editor.insertPlainText("new revision")
        with patch.object(self.window.pdf_panel, "load_pdf") as load_pdf:
            self._finish_success(tab, 2, b"%PDF-1.4 updated")

        load_pdf.assert_called_once_with(pdf, logical_key=manager.root_file)

    def test_displayed_final_banner_ignores_non_displayed_preview_failure(self) -> None:
        tab = self._add_doc("a.tex")
        self._finish_success(tab, 1)
        manager = tab.manager
        assert manager is not None

        self.window.preview_state.record_failed_attempt(manager.root_file)
        self.window._update_pdf_action_state()

        displayed = self.window.displayed_pdfs[manager.root_file]
        self.assertIs(displayed.purpose, BuildPurpose.FINAL)
        self.assertEqual(self._banner(), "PDF 已是最新")

    def test_failed_stale_preview_banner_preserves_failure_semantics(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None
        preview_pdf = manager.pdf_file_for(BuildPurpose.PREVIEW)
        preview_pdf.parent.mkdir(parents=True, exist_ok=True)
        preview_pdf.write_bytes(b"%PDF-1.4 preview")

        self.window.preview_state.begin_build(manager.root_file, 1)
        self.window.preview_state.finish_build(
            manager.root_file,
            1,
            success=True,
            pdf_file=preview_pdf,
            fidelity="proxy",
            manifest_digest="digest",
        )
        self.window.preview_state.mark_edited(manager.root_file)
        self.window.preview_state.begin_build(manager.root_file, 2)
        self.window.preview_state.finish_build(manager.root_file, 2, success=False)
        self.window._sync_pdf_panel_to_active_root()

        displayed = self.window.displayed_pdfs[manager.root_file]
        self.assertIs(displayed.purpose, BuildPurpose.PREVIEW)
        self.assertEqual(self._banner(), "预览失败，当前显示上次成功版本")

    def test_failure_after_success_keeps_old_pdf_with_stale_warning(self) -> None:
        tab = self._add_doc("a.tex")
        pdf = self._finish_success(tab, 1)
        manager = tab.manager
        assert manager is not None

        self.window.compile._emit_started(manager, manager.root_file, 2)
        self.window.compile.on_finished(
            self._result(manager, CompileOutcome.LATEX_ERROR, 2, returncode=1)
        )

        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        self.assertEqual(self._banner(), "编译未成功，当前显示上次成功版本")
        self.assertTrue(self.window.export_pdf_action.isEnabled())

    def test_stop_after_success_keeps_old_pdf_with_stale_warning(self) -> None:
        tab = self._add_doc("a.tex")
        pdf = self._finish_success(tab, 1)
        manager = tab.manager
        assert manager is not None

        self.window.compile._emit_started(manager, manager.root_file, 2)
        self.window.compile.on_finished(
            self._result(manager, CompileOutcome.STOPPED, 2, returncode=3)
        )

        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        self.assertEqual(self._banner(), "编译未成功，当前显示上次成功版本")
        self.assertIn("编译已停止", self.window.log_view.toPlainText())

    def test_first_compile_failure_shows_empty_panel_and_no_pdf(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None

        self.window.compile._emit_started(manager, manager.root_file, 1)
        self.window.compile.on_finished(
            self._result(manager, CompileOutcome.LATEX_ERROR, 1, returncode=1)
        )

        self.assertIsNone(self.window.pdf_panel.current_pdf)
        self.assertEqual(self._banner(), "编译未成功，暂无可用 PDF")
        self.assertFalse(self.window.export_pdf_action.isEnabled())
        self.assertFalse(self.window.export_pdf())

    def test_background_build_does_not_touch_active_tab_widgets(self) -> None:
        tab_a = self._add_doc("a.tex")
        self._add_doc("b.tex")  # active tab, uncompiled

        manager = tab_a.manager
        assert manager is not None
        manager.output_dir.mkdir(parents=True, exist_ok=True)
        manager.pdf_file.write_bytes(b"%PDF-1.4 A")
        with patch.object(self.window.pdf_panel, "load_pdf") as load_pdf:
            self.window.compile._emit_started(manager, manager.root_file, 1)
            self.window.compile.on_finished(
                self._result(manager, CompileOutcome.SUCCESS, 1)
            )

        load_pdf.assert_not_called()
        self.assertEqual(self._banner(), "尚未编译")
        self.assertFalse(self.window.export_pdf_action.isEnabled())

    def test_switch_to_uncompiled_tab_clears_viewer_and_blocks_export(self) -> None:
        tab_a = self._add_doc("a.tex")
        pdf_a = self._finish_success(tab_a, 1)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf_a)

        self._add_doc("b.tex")  # becomes active; has no build

        self.assertIsNone(self.window.pdf_panel.current_pdf)
        if self.window.pdf_panel._document is not None:
            self.assertIs(
                self.window.pdf_panel._stack.currentWidget(), self.window.pdf_panel._empty_state
            )
        self.assertEqual(self._banner(), "尚未编译")
        self.assertFalse(self.window.export_pdf_action.isEnabled())
        self.assertFalse(self.window.pdf_panel.export_pdf_button.isEnabled())
        with patch("app.gui.main_window.QFileDialog.getSaveFileName") as dialog:
            self.assertFalse(self.window.export_pdf())
        dialog.assert_not_called()

    def test_each_tab_loads_and_exports_only_its_own_pdf(self) -> None:
        tab_a = self._add_doc("a.tex")
        pdf_a = self._finish_success(tab_a, 1, b"%PDF-1.4 AAA")
        tab_b = self._add_doc("b.tex")
        pdf_b = self._finish_success(tab_b, 2, b"%PDF-1.4 BBB")
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf_b)

        index_a = self.window._index_for_tab_id(id(tab_a.editor))
        self.window.editor_tabs.setCurrentIndex(index_a)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf_a)
        exported = self.dir / "out-a.pdf"
        with patch(
            "app.gui.main_window.QFileDialog.getSaveFileName",
            return_value=(str(exported), ""),
        ):
            self.assertTrue(self.window.export_pdf())
        self.assertEqual(exported.read_bytes(), b"%PDF-1.4 AAA")

        index_b = self.window._index_for_tab_id(id(tab_b.editor))
        self.window.editor_tabs.setCurrentIndex(index_b)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf_b)
        exported_b = self.dir / "out-b.pdf"
        with patch(
            "app.gui.main_window.QFileDialog.getSaveFileName",
            return_value=(str(exported_b), ""),
        ):
            self.assertTrue(self.window.export_pdf())
        self.assertEqual(exported_b.read_bytes(), b"%PDF-1.4 BBB")

    def test_child_tabs_share_root_record_and_dirty_it(self) -> None:
        root_tab = self._add_doc("main.tex", "\\documentclass{article}\n\\input{child}\n\\input{part}\n")
        pdf = self._finish_success(root_tab, 1)
        root = root_tab.manager.root_file

        # Magic-root child shares the record: opening it keeps the root's PDF.
        child_path = self.dir / "child.tex"
        child_path.write_text("% !TEX root = main.tex\ntext", encoding="utf-8")
        child_tab = EditorTab(editor=self.window._make_editor("% !TEX root = main.tex\ntext"), path=child_path)
        self.window._add_tab(child_tab, child_path.name)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        self.assertEqual(self._banner(), "PDF 已是最新")

        child_tab.editor.insertPlainText("edited ")
        record = self.window.pdf_state.record_for(root)
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)
        self.assertEqual(self._banner(), "源码已修改，PDF 待更新")

        # \input child without a magic comment still dirties the known root record.
        self._finish_success(root_tab, 2)
        part_path = self.dir / "part.tex"
        part_path.write_text("part text", encoding="utf-8")
        part_tab = EditorTab(editor=self.window._make_editor("part text"), path=part_path)
        self.window._add_tab(part_tab, part_path.name)
        part_tab.editor.insertPlainText("more ")
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)

    def test_edit_during_build_never_shows_current(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None
        self.window.compile._emit_started(manager, manager.root_file, 1)
        self.assertEqual(self._banner(), "正在编译…")

        tab.editor.insertPlainText("edited during build")

        manager.output_dir.mkdir(parents=True, exist_ok=True)
        manager.pdf_file.write_bytes(b"%PDF-1.4 x")
        self.window.compile.on_finished(self._result(manager, CompileOutcome.SUCCESS, 1))

        self.assertEqual(self.window.pdf_panel.current_pdf, manager.pdf_file)
        self.assertEqual(self._banner(), "源码已修改，PDF 待更新")

    def test_late_result_from_older_build_is_ignored(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None
        pdf = self._finish_success(tab, 2)

        old_pdf = self.dir / "old.pdf"
        old_pdf.write_bytes(b"%PDF-1.4 old")
        stale = CompileResult(
            root_file=manager.root_file,
            output_dir=manager.output_dir,
            pdf_file=old_pdf,
            log_file=manager.log_file,
            command=[],
            returncode=0,
            stdout="",
            stderr="",
            duration_seconds=0.1,
            outcome=CompileOutcome.SUCCESS,
            errors=[],
            build_id=1,
        )
        with patch.object(self.window.pdf_panel, "load_pdf") as load_pdf:
            self.window.compile.on_finished(stale)

        load_pdf.assert_not_called()
        record = self.window.pdf_state.record_for(manager.root_file)
        self.assertEqual(record.last_successful_pdf, pdf)
        self.assertEqual(record.freshness, PdfFreshness.CURRENT)

    def test_clean_cache_clears_viewer_and_disables_actions(self) -> None:
        tab = self._add_doc("a.tex")
        self._finish_success(tab, 1)
        self.assertTrue(self.window.export_pdf_action.isEnabled())

        self.assertTrue(self.window.clean_build_cache())

        self.assertIsNone(self.window.pdf_panel.current_pdf)
        self.assertEqual(self._banner(), "尚未编译")
        self.assertFalse(self.window.export_pdf_action.isEnabled())
        self.assertFalse(self.window.pdf_panel.export_pdf_button.isEnabled())

    def test_atomic_export_failure_leaves_no_partial_files(self) -> None:
        tab = self._add_doc("a.tex")
        self._finish_success(tab, 1)
        target = self.dir / "exported.pdf"

        with patch("app.gui.pdf_export_controller.shutil.copy2", side_effect=OSError("disk full")), patch(
            "app.gui.main_window.QFileDialog.getSaveFileName",
            return_value=(str(target), ""),
        ), patch("app.gui.main_window.QMessageBox.warning") as warning:
            self.assertFalse(self.window.export_pdf())

        warning.assert_called_once()
        self.assertFalse(target.exists())
        self.assertEqual(list(self.dir.glob("*.part")), [])
        self.assertEqual(list(self.dir.glob("*.pdf.part")), [])

    def test_log_headline_matches_outcome_and_leads_with_first_error(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None
        footer = "Latexmk: Errors, so did not complete cycle"
        self.window.compile._emit_started(manager, manager.root_file, 1)
        self.window.compile.on_finished(
            self._result(
                manager,
                CompileOutcome.LATEX_ERROR,
                1,
                returncode=12,
                stderr=footer,
                errors=[LaTeXError(message="Undefined control sequence \\foo", line=3)],
            )
        )

        log_text = self.window.log_view.toPlainText()
        self.assertIn("编译失败：", log_text)
        headline_index = log_text.index("编译失败：")
        footer_index = log_text.index("Latexmk")
        self.assertLess(headline_index, footer_index)
        first_line = next(line for line in log_text.splitlines() if line.startswith("编译失败："))
        self.assertNotIn("Latexmk", first_line)

    def test_missing_toolchain_compile_updates_active_root_state(self) -> None:
        tab = self._add_doc("a.tex")
        self.window.toolchain = LaTeXToolchain(
            latexmk=None, pdflatex=None, texcount=None, synctex=None
        )
        self.window.compile_current()
        record = self.window.pdf_state.record_for(tab.manager.root_file)
        self.assertEqual(record.last_outcome, CompileOutcome.TOOLCHAIN_MISSING)
        self.assertEqual(self._banner(), "编译未成功，暂无可用 PDF")
        self.assertFalse(self.window.export_pdf_action.isEnabled())

    def test_external_reload_marks_pdf_dirty_immediately(self) -> None:
        tab = self._add_doc("a.tex", "original")
        pdf = self._finish_success(tab, 1)
        self.assertEqual(self._banner(), "PDF 已是最新")

        assert tab.path is not None and tab.manager is not None
        tab.path.write_text("changed on disk", encoding="utf-8")
        with patch.object(tab.manager, "schedule_compile"):
            self.window.reload_external_change(str(tab.path))

        self.assertEqual(tab.editor.toPlainText(), "changed on disk")
        self.assertEqual(self._banner(), "源码已修改，PDF 待更新")
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)
        record = self.window.pdf_state.record_for(tab.manager.root_file)
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)

    def test_background_build_does_not_touch_compile_indicators(self) -> None:
        tab_a = self._add_doc("a.tex")
        self._add_doc("b.tex")  # active
        manager = tab_a.manager
        assert manager is not None

        self.window.compile._emit_started(manager, manager.root_file, 1)

        self.assertIsNone(self.window.compile_started_at)
        self.assertFalse(self.window.stop_compile_action.isEnabled())
        self.assertFalse(self.window.compile_timer.isActive())
        self.assertNotIn("正在", self.window.statusBar().currentMessage())
        self.assertEqual(self.window.compile_time_label.text(), "空闲")

        manager.output_dir.mkdir(parents=True, exist_ok=True)
        manager.pdf_file.write_bytes(b"%PDF-1.4 A")
        self.window.compile.on_finished(self._result(manager, CompileOutcome.SUCCESS, 1))
        self.assertEqual(self.window.compile_time_label.text(), "空闲")

    def test_compile_indicators_follow_active_tab(self) -> None:
        tab_a = self._add_doc("a.tex")
        tab_b = self._add_doc("b.tex")  # active
        manager_b = tab_b.manager
        assert manager_b is not None

        self.window.compile._emit_started(manager_b, manager_b.root_file, 1)
        self.assertTrue(self.window.stop_compile_action.isEnabled())
        self.assertIsNotNone(self.window.compile_started_at)

        self.window.editor_tabs.setCurrentIndex(self.window._index_for_tab_id(id(tab_a.editor)))
        self.assertFalse(self.window.stop_compile_action.isEnabled())
        self.assertIsNone(self.window.compile_started_at)

        self.window.editor_tabs.setCurrentIndex(self.window._index_for_tab_id(id(tab_b.editor)))
        self.assertTrue(self.window.stop_compile_action.isEnabled())
        self.assertIsNotNone(self.window.compile_started_at)

        manager_b.output_dir.mkdir(parents=True, exist_ok=True)
        manager_b.pdf_file.write_bytes(b"%PDF-1.4 B")
        self.window.compile.on_finished(self._result(manager_b, CompileOutcome.SUCCESS, 1))
        self.assertFalse(self.window.stop_compile_action.isEnabled())

    def test_root_and_child_share_one_compile_manager(self) -> None:
        main = self.dir / "main.tex"
        main.write_text("\\documentclass{article}\n\\input{child}\n", encoding="utf-8")
        child = self.dir / "child.tex"
        child.write_text("% !TEX root = main.tex\ntext", encoding="utf-8")

        manager_main = self.window.create_compile_manager(main)
        manager_child = self.window.create_compile_manager(child)

        self.assertIs(manager_main, manager_child)
        self.assertEqual(manager_main.root_file, main.resolve())

    def test_plain_input_child_shares_parent_compile_manager(self) -> None:
        main = self.dir / "main.tex"
        main.write_text("\\documentclass{article}\n\\begin{document}\n\\input{child}\n\\end{document}", encoding="utf-8")
        child = self.dir / "child.tex"
        child.write_text("text without magic root", encoding="utf-8")

        manager_main = self.window.create_compile_manager(main)
        manager_child = self.window.create_compile_manager(child)

        self.assertIs(manager_main, manager_child)
        self.assertEqual(manager_child.root_file, main.resolve())

    def test_closing_child_tab_keeps_shared_manager_running(self) -> None:
        main_tab = self._add_doc("main.tex", "\\documentclass{article}\n\\input{child}\n")
        child_path = self.dir / "child.tex"
        child_path.write_text("% !TEX root = main.tex\ntext", encoding="utf-8")
        child_tab = EditorTab(editor=self.window._make_editor("text"), path=child_path)
        self.window._add_tab(child_tab, child_path.name)
        child_tab.manager = self.window.create_compile_manager(child_path)
        self.assertIs(child_tab.manager, main_tab.manager)

        manager = main_tab.manager
        assert manager is not None
        with patch.object(manager, "stop_current") as stop_current:
            self.window.close_tab(self.window._index_for_tab_id(id(child_tab.editor)))
            stop_current.assert_not_called()
            self.assertIn(manager.root_file, self.window.compile_managers)
            self.window.close_tab(self.window._index_for_tab_id(id(main_tab.editor)))
            stop_current.assert_called_once()
        self.assertNotIn(manager.root_file, self.window.compile_managers)

    def test_clean_cache_invalidates_in_flight_result(self) -> None:
        tab = self._add_doc("a.tex")
        manager = tab.manager
        assert manager is not None
        self._finish_success(tab, 1)

        self.window.compile._emit_started(manager, manager.root_file, 2)
        self.assertTrue(self.window.clean_build_cache())
        self.assertEqual(self._banner(), "尚未编译")

        self.window.compile.on_finished(
            self._result(manager, CompileOutcome.STOPPED, 2, returncode=-15)
        )

        record = self.window.pdf_state.record_for(manager.root_file)
        self.assertEqual(record.freshness, PdfFreshness.UNCOMPILED)
        self.assertEqual(self._banner(), "尚未编译")
        self.assertFalse(self.window.export_pdf_action.isEnabled())

    def test_save_as_rebinds_pdf_state_to_new_root(self) -> None:
        tab = self._add_doc("a.tex")
        old_manager = tab.manager
        assert old_manager is not None
        pdf_a = self._finish_success(tab, 1)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf_a)

        new_path = self.dir / "renamed.tex"
        with patch(
            "app.gui.main_window.QFileDialog.getSaveFileName",
            return_value=(str(new_path), ""),
        ):
            self.assertTrue(self.window.save_current_as())

        self.assertEqual(tab.path, new_path.resolve())
        self.assertIsNot(tab.manager, old_manager)
        self.assertNotIn(old_manager.root_file, self.window.compile_managers)
        self.assertIsNone(self.window.pdf_panel.current_pdf)
        self.assertEqual(self._banner(), "尚未编译")
        self.assertFalse(self.window.export_pdf_action.isEnabled())
        with patch("app.gui.main_window.QFileDialog.getSaveFileName") as dialog:
            self.assertFalse(self.window.export_pdf())
        dialog.assert_not_called()

    def test_deep_nested_child_edit_marks_root_dirty(self) -> None:
        (self.dir / "chapters").mkdir()
        root_tab = self._add_doc("main.tex", "\\documentclass{article}\n\\input{chapters/ch1}\n")
        chapter = self.dir / "chapters" / "ch1.tex"
        chapter.write_text("\\input{sec1}", encoding="utf-8")
        section = self.dir / "chapters" / "sec1.tex"
        section.write_text("deep text", encoding="utf-8")
        self._finish_success(root_tab, 1)
        root = root_tab.manager.root_file

        section_tab = EditorTab(editor=self.window._make_editor("deep text"), path=section)
        self.window._add_tab(section_tab, section.name)
        section_tab.editor.insertPlainText("edited ")

        record = self.window.pdf_state.record_for(root)
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)

    def test_synctex_never_falls_back_to_foreign_pdf(self) -> None:
        tab_a = self._add_doc("a.tex")
        pdf_a = self._finish_success(tab_a, 1)
        self._add_doc("b.tex")  # active, uncompiled

        # Even a stale viewer path must not drive SyncTeX for another root.
        self.window.pdf_panel.current_pdf = pdf_a
        with patch("app.gui.main_window.pdf_to_source") as pdf_to_source:
            self.window.sync_pdf_to_source(1, 10.0, 10.0)
        pdf_to_source.assert_not_called()

    def test_reveal_pdf_failure_shows_hint_instead_of_raising(self) -> None:
        tab = self._add_doc("a.tex")
        self._finish_success(tab, 1)

        with patch(
            "app.gui.main_window.subprocess.Popen", side_effect=OSError("no file manager")
        ), patch("app.gui.main_window.QDesktopServices.openUrl", return_value=False):
            self.window.reveal_pdf()  # must not raise

        self.assertIn("无法打开文件管理器", self.window.log_view.toPlainText())


class FormulaComposerTests(TestCase):
    """Focused tests for the DS-001 formula composer GUI slice."""

    def setUp(self) -> None:
        app()

    def _window_with_document(self, text: str) -> tuple[MainWindow, EditorTab]:
        window = MainWindow(settings_store=isolated_settings())
        window.auto_compile_action.setChecked(False)
        editor = window._make_editor(text)
        tab = EditorTab(editor=editor)
        window._add_tab(tab, "formula_test.tex")
        return window, tab

    @staticmethod
    def _select(editor: LaTeXEditor, start: int, end: int) -> None:
        cursor = editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

    @staticmethod
    def _close(window: MainWindow, tab: EditorTab) -> None:
        tab.modified = False
        tab.dirty = False
        window.close()

    def test_apply_plan_replaces_formula_and_merges_package_into_one_undo(self) -> None:
        source = "\\documentclass{article}\n\\begin{document}\nText $a+b$ here\n\\end{document}\n"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index("$")
        end = start + len("$a+b$")

        envelope = parse_document_selection(source, start, end)
        assert envelope is not None
        fraction = apply_formula_template(
            FormulaDraft(mode=envelope.mode, body=envelope.body), "fraction"
        )
        assert fraction is not None
        draft = FormulaDraft(mode=FormulaMode.EQUATION_STAR, body=fraction.draft.body)
        plan = final_edit_plan(
            source,
            start,
            end,
            draft,
            body_cursor_offset=fraction.cursor_offset,
        )
        assert plan is not None
        self.assertEqual(plan.packages, ("amsmath",))

        applied = window.insertions.apply_formula_plan(tab, plan)

        self.assertTrue(applied)
        text = editor.toPlainText()
        self.assertIn("\\usepackage{amsmath}", text)
        self.assertIn("\\begin{equation*}\\frac{a+b}{}\\end{equation*}", text)
        self.assertNotIn("$a+b$", text)
        # A single Undo step restores both the package and the formula text.
        editor.undo()
        self.assertEqual(editor.toPlainText(), source)
        self._close(window, tab)

    def test_apply_plan_refuses_stale_selection(self) -> None:
        source = "Text $a+b$ here"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index("$")
        end = start + len("$a+b$")
        plan = final_edit_plan(
            source,
            start,
            end,
            FormulaDraft(mode=FormulaMode.INLINE_DOLLAR, body="a+b"),
        )
        assert plan is not None

        editor.setPlainText("Text $x+y$ here")  # external edit at the same offsets
        with patch("app.gui.insertion_actions.QMessageBox.warning") as warning:
            applied = window.insertions.apply_formula_plan(tab, plan)

        self.assertFalse(applied)
        self.assertEqual(editor.toPlainText(), "Text $x+y$ here")
        warning.assert_called_once()
        self._close(window, tab)

    def test_composer_requires_exact_formula_selection(self) -> None:
        source = "Text $a+b$ here"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        self._select(editor, 0, len(source))

        with patch("app.gui.insertion_actions.QMessageBox.information") as information:
            window.open_formula_composer()

        self.assertEqual(editor.toPlainText(), source)
        information.assert_called_once()
        self._close(window, tab)

    def test_composer_without_selection_opens_dialog_and_inserts_new_formula(self) -> None:
        source = "\\documentclass{article}\n\\begin{document}\n\n\\end{document}\n"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        position = len(source) - len("\\end{document}\n")
        cursor = editor.textCursor()
        cursor.setPosition(position)
        editor.setTextCursor(cursor)

        with patch("app.gui.insertion_actions.FormulaDialog") as dialog_cls:
            dialog_cls.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialog_cls.return_value.plan.return_value = final_edit_plan(
                source,
                position,
                position,
                FormulaDraft(mode=FormulaMode.EQUATION, body=""),
                body_cursor_offset=0,
            )
            window.open_formula_composer()

        _, kwargs = dialog_cls.call_args
        self.assertEqual(kwargs.get("seed_text"), r"\begin{equation}\end{equation}")
        self.assertIn(r"\begin{equation}\end{equation}", editor.toPlainText())
        editor.undo()
        self.assertEqual(editor.toPlainText(), source)
        self._close(window, tab)

    def test_toolbox_equation_button_routes_through_composer(self) -> None:
        source = "\\documentclass{article}\n\\begin{document}\n\n\\end{document}\n"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        cursor = editor.textCursor()
        cursor.setPosition(len(source) - len("\\end{document}\n"))
        editor.setTextCursor(cursor)

        with patch("app.gui.insertion_actions.FormulaDialog") as dialog_cls:
            dialog_cls.return_value.exec.return_value = QDialog.DialogCode.Rejected
            window.insert_panel.equationRequested.emit()

        dialog_cls.assert_called_once()
        self.assertEqual(editor.toPlainText(), source)
        self._close(window, tab)

    def test_dialog_seeds_from_selection_and_builds_plan(self) -> None:
        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        self.assertEqual(dialog.visual_edit.latex(), "a+b")
        self.assertTrue(dialog.apply_template("fraction"))
        self.assertEqual(dialog.visual_edit.latex(), r"a+b\frac{}{}")
        self.assertTrue(dialog.set_mode(FormulaMode.EQUATION))

        plan = dialog.build_plan()
        assert plan is not None
        self.assertEqual(plan.start, start)
        self.assertEqual(plan.end, end)
        self.assertEqual(plan.text, r"\begin{equation}a+b\frac{}{}\end{equation}")
        dialog.close()

    def test_dialog_apply_is_idempotent(self) -> None:
        source = r"Before \(E=mc^2\) after."
        seed = r"\(E=mc^2\)"
        start = source.index(seed)
        end = start + len(seed)
        dialog = FormulaDialog(None, source, start, end)

        original_accept = QDialog.accept
        accept_calls: list = []

        def spy(self) -> None:
            accept_calls.append(self)
            original_accept(self)

        with patch.object(QDialog, "accept", new=spy):
            dialog._on_apply()
            dialog._on_apply()
        self.assertEqual(len(accept_calls), 1)
        self.assertTrue(dialog._submitted)
        self.assertIsNotNone(dialog.plan())
        self.assertFalse(dialog._ok_button.isEnabled())
        dialog.close()

    def test_ocr_button_ignores_rapid_repeated_clicks(self) -> None:
        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        with patch.object(FormulaDialog, "_get_ocr_manager", return_value=object()), patch(
            "app.gui.formula_ocr.batch_dialog.BatchRecognitionDialog"
        ) as dialog_cls:
            instance = dialog_cls.return_value
            instance.exec.return_value = QDialog.DialogCode.Rejected
            dialog._open_batch_ocr()
            dialog._open_batch_ocr()
        self.assertEqual(dialog_cls.call_count, 1)
        self.assertTrue(dialog.ocr_button.isEnabled())
        self.assertFalse(dialog._ocr_open)

        dialog._ocr_ts = 0.0  # debounce window expired
        with patch.object(FormulaDialog, "_get_ocr_manager", return_value=object()), patch(
            "app.gui.formula_ocr.batch_dialog.BatchRecognitionDialog"
        ) as dialog_cls:
            instance = dialog_cls.return_value
            instance.exec.return_value = QDialog.DialogCode.Rejected
            dialog._open_batch_ocr()
        self.assertEqual(dialog_cls.call_count, 1)
        dialog.close()

    def test_dialog_rejects_template_and_plan_on_invalid_text(self) -> None:
        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        dialog.source_mode_check.setChecked(True)
        dialog.source_edit.setPlainText("$a$ $b$")
        self.assertFalse(dialog.apply_template("fraction"))
        self.assertEqual(dialog.source_edit.toPlainText(), "$a$ $b$")
        self.assertIsNone(dialog.build_plan())
        self.assertIsNone(dialog.plan())
        dialog.close()

    def test_dialog_accepts_explicit_seed_text_for_insertion(self) -> None:
        source = "Text here"
        dialog = FormulaDialog(
            None,
            source,
            4,
            4,
            seed_text=r"\begin{equation}\end{equation}",
        )

        self.assertEqual(dialog.visual_edit.latex(), "")
        self.assertTrue(dialog.apply_template("fraction"))
        self.assertEqual(dialog.visual_edit.latex(), r"\frac{}{}")
        plan = dialog.build_plan()
        assert plan is not None
        self.assertEqual(plan.start, 4)
        self.assertEqual(plan.end, 4)
        self.assertEqual(plan.source_text, "")
        self.assertEqual(plan.text, r"\begin{equation}\frac{}{}\end{equation}")
        dialog.close()

    def test_dialog_paste_into_visual_editor(self) -> None:
        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        dialog.visual_edit.paste_clipboard(r"\cdot c")
        plan = dialog.build_plan()

        assert plan is not None
        self.assertEqual(plan.text, r"$a+b\cdot c$")
        dialog.close()

    def test_keyboard_fraction_button_inserts_structure(self) -> None:
        from app.gui.math_keyboard import MathKeyButton

        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        fraction_button = next(
            button
            for button in dialog.keyboard.findChildren(MathKeyButton)
            if button.action == "structure:fraction"
        )
        fraction_button.click()

        self.assertEqual(dialog.visual_edit.latex(), r"a+b\frac{}{}")
        self.assertEqual(dialog.keyboard.isEnabled(), True)
        dialog.close()

    def test_keyboard_digits_and_symbols_insert_text(self) -> None:
        from app.gui.math_keyboard import MathKeyButton

        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        actions = {
            button.action: button
            for button in dialog.keyboard.findChildren(MathKeyButton)
        }
        actions["text:7"].click()
        actions["text:+"].click()
        actions["text:8"].click()
        actions["command:times"].click()
        actions["command:pi"].click()

        self.assertEqual(dialog.visual_edit.latex(), r"a+b7+8\times\pi")
        dialog.close()

    def test_keyboard_category_switch_preserves_formula(self) -> None:
        from app.gui.math_keyboard import MathKeyButton

        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        sqrt_button = next(
            button
            for button in dialog.keyboard.findChildren(MathKeyButton)
            if button.action == "structure:sqrt"
        )
        sqrt_button.click()
        self.assertEqual(dialog.visual_edit.latex(), r"a+b\sqrt{}")

        from PySide6.QtWidgets import QPushButton

        greek_button = next(
            button
            for button in dialog.keyboard.findChildren(QPushButton)
            if button.text() == "希腊字母"
        )
        greek_button.click()

        self.assertEqual(dialog.visual_edit.latex(), r"a+b\sqrt{}")
        dialog.close()

    def test_keyboard_disabled_in_source_mode(self) -> None:
        source = "Text $a+b$ here"
        start = source.index("$")
        end = start + len("$a+b$")
        dialog = FormulaDialog(None, source, start, end)

        dialog.source_mode_check.setChecked(True)
        self.assertFalse(dialog.keyboard.isEnabled())
        dialog.source_mode_check.setChecked(False)
        self.assertTrue(dialog.keyboard.isEnabled())
        dialog.close()

    def test_acceptance_inline_fraction_never_forces_newline(self) -> None:
        source = r"The result is \(\) under this condition."
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index(r"\(")
        end = start + len(r"\(\)")
        self._select(editor, start, end)

        class InlineFractionDialog(FormulaDialog):
            def exec(self) -> QDialog.DialogCode:
                self.visual_edit.insert_structure("fraction")
                self.visual_edit.type_key("a")
                self.visual_edit.cursor_tab()
                self.visual_edit.type_key("b")
                self.set_mode(FormulaMode.INLINE_PAREN)
                self._on_apply()
                return QDialog.DialogCode.Accepted

        with patch("app.gui.insertion_actions.FormulaDialog", InlineFractionDialog):
            window.open_formula_composer()

        text = editor.toPlainText()
        self.assertEqual(text, r"The result is \(\frac{a}{b}\) under this condition.")
        self.assertNotIn("\n", text)
        self._close(window, tab)

    def test_acceptance_read_back_and_modify_formula(self) -> None:
        source = r"See \(E=mc^2\) here."
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index(r"\(")
        end = start + len(r"\(E=mc^2\)")
        self._select(editor, start, end)

        class ModifyDialog(FormulaDialog):
            def exec(self) -> QDialog.DialogCode:
                self.visual_edit.cursor_home()
                self.visual_edit.cursor_right()  # enter the base slot
                self.visual_edit.cursor_right()
                self.visual_edit.cursor_right()  # right after "E="
                for char in ("\\", "g", "a", "m", "m", "a", " "):
                    self.visual_edit.type_key(char)
                self._on_apply()
                return QDialog.DialogCode.Accepted

        with patch("app.gui.insertion_actions.FormulaDialog", ModifyDialog):
            window.open_formula_composer()

        self.assertEqual(editor.toPlainText(), r"See \(E=\gamma mc^2\) here.")
        self._close(window, tab)

    def test_composer_end_to_end_apply_via_dialog(self) -> None:
        source = "Text $a+b$ here"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index("$")
        end = start + len("$a+b$")
        self._select(editor, start, end)

        class FakeDialog:
            def __init__(self, _parent, document_text: str, sel_start: int, sel_end: int) -> None:
                self._document_text = document_text
                self._sel_start = sel_start
                self._sel_end = sel_end

            def exec(self) -> QDialog.DialogCode:
                return QDialog.DialogCode.Accepted

            def plan(self):
                envelope = parse_document_selection(
                    self._document_text, self._sel_start, self._sel_end
                )
                assert envelope is not None
                fraction = apply_formula_template(
                    FormulaDraft(mode=envelope.mode, body=envelope.body), "fraction"
                )
                assert fraction is not None
                return final_edit_plan(
                    self._document_text,
                    self._sel_start,
                    self._sel_end,
                    fraction.draft,
                    body_cursor_offset=fraction.cursor_offset,
                )

        with patch("app.gui.insertion_actions.FormulaDialog", FakeDialog):
            window.open_formula_composer()

        self.assertIn(r"$\frac{a+b}{}$", editor.toPlainText())
        self.assertNotIn("$a+b$", editor.toPlainText())
        # Cursor lands inside the empty denominator slot: 1 ($) + 11 (body offset).
        self.assertEqual(editor.textCursor().position(), start + 12)
        self._close(window, tab)

    def test_cancel_leave_editor_untouched(self) -> None:
        source = "Text $a+b$ here"
        window, tab = self._window_with_document(source)
        editor = tab.editor
        start = source.index("$")
        end = start + len("$a+b$")
        self._select(editor, start, end)

        with patch(
            "app.gui.insertion_actions.FormulaDialog.exec",
            return_value=QDialog.DialogCode.Rejected,
        ):
            window.open_formula_composer()

        self.assertEqual(editor.toPlainText(), source)
        self._close(window, tab)

    def test_images_refresh_uses_incremental_index(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            figures = root / "figures"
            figures.mkdir()
            (figures / "a.png").write_bytes(b"png-asset")
            source = root / "main.tex"
            source.write_text(
                "\\documentclass{article}\n\\begin{document}\n\\end{document}\n",
                encoding="utf-8",
            )
            window = MainWindow(settings_store=isolated_settings())
            window.auto_compile_action.setChecked(False)
            editor = window._make_editor(source.read_text(encoding="utf-8"))
            tab = EditorTab(editor=editor, path=source)
            window._add_tab(tab, source.name)

            window.refresh_project_panels()
            self.assertEqual(window.images_panel.table.rowCount(), 1)
            self.assertTrue((root / ".icstex" / "asset-index.json").exists())

            window.refresh_project_panels()
            self.assertEqual(window.images_panel.table.rowCount(), 1)
            tab.modified = False
            tab.dirty = False
            window.close()

    def test_import_perf_dialog_shows_summaries(self) -> None:
        from app.core.import_metrics import import_metrics
        from app.gui.import_perf_dialog import ImportPerfDialog

        recorder = import_metrics.begin_transaction("perf-test")
        import_metrics.record_compile_request("asset_import")
        import_metrics.record_compile_start("preview")
        import_metrics.record_compile_finish("preview")

        dialog = ImportPerfDialog(None)
        text = dialog.text.toPlainText()
        self.assertIn("perf-test", text)
        self.assertIn("compile requested=1", text)
        self.assertIn("started=1", text)
        dialog.close()
