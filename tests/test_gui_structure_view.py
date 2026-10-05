from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from dataclasses import replace
from unittest.mock import patch

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtGui import QAccessible, QAccessibleActionInterface
from PySide6.QtWidgets import QStyleOptionViewItem, QLineEdit, QMessageBox
from PySide6.QtTest import QTest

from app.core.document_structure import SourceEdit, parse_structure
from app.core.text_positions import utf16_length
from app.gui.main_window import MainWindow
from app.gui.structure_view import ROLE
from tests.test_gui_editor import app, isolated_settings, wait_until
from tests.test_document_structure import SAMPLE


class StructureViewTests(TestCase):
    def setUp(self):
        self.app = app()
        self.temp = TemporaryDirectory(prefix="icstex-structure-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / "main.tex"
        self.file.write_text(SAMPLE, encoding="utf-8")
        self.window = MainWindow(settings_store=isolated_settings())
        self.window.save_debounce_ms = 3600000
        self.window.auto_compile_action.setChecked(False)
        self.window.open_file(self.file)
        self.view = self.window.structure
        self.editor = self.window.current_tab().editor
        self.addCleanup(self.dispose)

    def dispose(self):
        for tab in self.window.tabs.values():
            self.window.documents.cancel_save_timer(tab)
            tab.modified = tab.dirty = False
        self.window.close()
        self.window.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def structure(self):
        self.view.set_active(True)
        self.assertTrue(wait_until(lambda: self.view._snapshot_key == self.view._key()))

    def settle(self):
        self.assertTrue(wait_until(lambda: self.view._snapshot_key == self.view._key()))

    def select(self, kind):
        block = next(b for b in self.view.snapshot.walk() if b.kind == kind)
        self.view.tree.setCurrentItem(self.view._items[block.start])
        return block

    def test_switch_keeps_document_and_does_not_save_or_compile(self):
        cursor = self.editor.textCursor()
        cursor.setPosition(utf16_length(SAMPLE[:SAMPLE.index("E=mc")]))
        self.editor.setTextCursor(cursor)
        position = cursor.position()
        with patch.object(self.window.compile, "compile_current") as compile_call:
            self.structure()
            self.assertIs(self.window.current_tab().editor, self.editor)
            self.assertIs(self.window.source_stack.currentWidget(), self.view.page)
            self.assertEqual(self.view.selected_block().kind, "formula")
            self.view.set_active(False)
            self.assertIs(self.window.source_stack.currentWidget(), self.window.editor_tabs)
            self.assertEqual(self.editor.textCursor().position(), position)
            compile_call.assert_not_called()
        self.assertEqual(self.editor.toPlainText(), SAMPLE)
        self.assertEqual(self.file.read_text(), SAMPLE)

    def test_edit_uses_same_undo_history_and_preserves_unrelated_source(self):
        self.structure()
        self.select("title")
        self.view.edit_selected()
        self.assertIs(self.view.content_stack.currentWidget(), self.view.local_editor)
        self.view.local_editor.text.setPlainText("新标题😀")
        self.assertEqual(self.editor.toPlainText(), SAMPLE.replace("标题😀", "新标题😀"))
        self.settle()
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), SAMPLE)
        self.editor.redo()
        self.assertIn("新标题😀", self.editor.toPlainText())

    def test_nested_move_and_undo(self):
        self.structure()
        first, second = self.view.snapshot.blocks[1:]
        self.view.move(first, second, "inside")
        self.assertIn(r"\subsection{方法}", self.editor.toPlainText())
        self.assertIn(r"\subsubsection*{数据}", self.editor.toPlainText())
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), SAMPLE)

    def test_add_block_joins_source_and_undo(self):
        self.structure()
        self.select("section")
        self.view.add_block("text")
        self.assertIn("在这里写正文。", self.editor.toPlainText())
        self.editor.undo()
        self.assertEqual(self.editor.toPlainText(), SAMPLE)

    def test_code_navigation_is_exact_with_non_bmp_characters(self):
        self.structure()
        block = self.select("formula")
        self.view.show_selected_source()
        self.assertFalse(self.view.active)
        self.assertFalse(self.editor.textCursor().hasSelection())
        self.assertEqual(self.editor._sync_selection.cursor.selectedText(), SAMPLE[block.start:block.end])
        self.view.set_active(True)
        self.settle()
        self.assertEqual(self.view.selected_block().start, block.start)

    def test_native_accessibility_toggle_changes_view_not_only_checkmark(self):
        self.structure()
        action = QAccessible.queryAccessibleInterface(self.view.code_button).actionInterface()
        action.doAction(QAccessibleActionInterface.toggleAction())
        self.assertFalse(self.view.active)
        self.assertIs(self.window.source_stack.currentWidget(), self.window.editor_tabs)
        self.assertFalse(self.view.structure_button.isChecked())
        self.assertTrue(self.view.code_button.isChecked())
        action = QAccessible.queryAccessibleInterface(self.view.structure_button).actionInterface()
        action.doAction(QAccessibleActionInterface.toggleAction())
        self.assertTrue(self.view.active)
        self.assertIs(self.window.source_stack.currentWidget(), self.view.page)

    def test_open_and_return_without_typing_does_not_write(self):
        self.structure()
        self.select("title")
        self.view.edit_selected()
        self.view.leave_local_editor()
        self.editor.setReadOnly(True)
        self.view.add_block("text")
        self.assertEqual(self.editor.toPlainText(), SAMPLE)

    def test_edit_undo_does_not_reauthorize_old_binding(self):
        self.structure()
        self.select("title")
        self.view.edit_selected()
        self.editor.insertPlainText("changed")
        self.editor.undo()
        self.view.local_editor.text.setPlainText("must not apply")
        self.assertEqual(self.editor.toPlainText(), SAMPLE)
        self.assertIsNone(self.view.local_editor.key)

    def test_source_typing_does_not_parse_when_structure_hidden(self):
        self.structure()
        self.view.set_active(False)
        with patch("app.gui.structure_view.parse_structure") as parser:
            for _ in range(10):
                self.editor.insertPlainText("a")
            self.app.processEvents()
            self.assertFalse(self.view._timer.isActive())
            parser.assert_not_called()

    def test_tab_switch_rejects_late_result(self):
        self.structure()
        old_key, old_snapshot = self.view._key(), self.view.snapshot
        self.window.new_document()
        new_editor = self.window.current_tab().editor
        self.view._running = old_key
        self.view._finished(old_key, old_snapshot)
        self.assertIs(self.view._editor, new_editor)
        self.assertNotEqual(self.view._snapshot_key, old_key)
        self.assertEqual(self.editor.toPlainText(), SAMPLE)

    def test_local_preview_never_compiles_a_stale_pdf(self):
        self.structure()
        self.select("formula")
        with patch.object(self.window, "_current_synctex_pdf", return_value=None), patch.object(
                self.window.compile, "compile_current") as compile_call:
            self.view.set_local_preview(True)
            self.assertIn("最新 PDF", self.view.hint.text())
            compile_call.assert_not_called()

    def test_leaving_stale_local_preview_restores_whole_width(self):
        self.structure()
        self.view.local_preview = True
        self.window.pdf_panel._has_pages = True
        with patch.object(self.window, "_current_synctex_pdf", return_value=None), patch.object(
                self.window.pdf_panel, "fit_width") as fit:
            self.view.set_local_preview(False)
            fit.assert_called_once()
        self.assertFalse(self.view.local_button.isChecked())
        self.assertTrue(self.view.global_button.isChecked())

    def test_return_after_typing_formula_end_selects_formula(self):
        self.structure()
        block = self.select("formula")
        self.view.show_selected_source()
        self.editor.setTextCursor(self.editor._sync_selection.cursor)
        self.editor.insertPlainText(r"\[x+1\]")
        self.view.set_active(True)
        self.settle()
        self.assertEqual(self.view.selected_block().kind, "formula")

    def test_closed_controller_ignores_worker_result(self):
        self.structure()
        key = self.view._key()
        snapshot = self.view.snapshot
        self.view.shutdown()
        self.view._running = key
        self.view._finished(key, parse_structure("different"))
        self.assertIs(self.view.snapshot, snapshot)

    def test_save_from_structure_uses_normal_file_path(self):
        self.structure()
        self.select("section")
        self.view.add_block("text")
        self.assertTrue(self.window.save_current())
        self.assertEqual(self.file.read_text(), self.editor.toPlainText())
        self.assertFalse((self.root / ".icstex" / "blocks.json").exists())

    def test_wrapped_table_preview_is_not_forced_into_a_short_row(self):
        self.structure()
        block = self.select("table")
        item = self.view._items[block.start]
        rows = tuple(("long cell text " * 8, "value") for _ in range(6))
        item.setData(0, ROLE, replace(block, rows=rows))
        index = self.view.tree.indexFromItem(item)
        delegate = self.view.tree.itemDelegate()
        size = delegate.sizeHint(QStyleOptionViewItem(), index)
        document = delegate._document(index, size.width())
        self.assertGreater(size.height(), 154)
        self.assertGreaterEqual(size.height(), document.size().height() + 18)

    def test_navigation_reveals_source_instead_of_a_hidden_editor(self):
        self.structure()
        self.window.project_panels.jump_to_outline(8)
        self.assertFalse(self.view.active)
        self.assertIs(self.window.source_stack.currentWidget(), self.window.editor_tabs)
        self.assertEqual(self.editor.textCursor().blockNumber(), 7)
        self.structure()
        self.window.open_file(self.file, 12)
        self.assertFalse(self.view.active)
        self.assertEqual(self.editor.textCursor().blockNumber(), 11)
        self.assertEqual(self.editor.toPlainText(), SAMPLE)

    def test_delete_keyboard_and_undo_preserve_other_blocks(self):
        self.structure()
        block = self.select("formula")
        QTest.keyClick(self.view.tree, Qt.Key.Key_Backspace)
        self.assertEqual(self.editor.toPlainText(), SAMPLE[:block.start] + SAMPLE[block.end:])
        self.view.undo_source()
        self.assertEqual(self.editor.toPlainText(), SAMPLE)

    def test_section_delete_cancel_and_stale_confirmation(self):
        self.structure()
        self.select("section")
        with patch.object(QMessageBox, "exec"):
            self.view.delete_selected()
        self.assertEqual(self.editor.toPlainText(), SAMPLE)
        def change(box):
            self.editor.insertPlainText("changed")
            self.editor.undo()
        with patch.object(QMessageBox, "exec", change), patch.object(
                QMessageBox, "clickedButton", lambda box: next(
                    button for button in box.buttons() if box.buttonRole(button) == QMessageBox.ButtonRole.DestructiveRole)):
            self.view.delete_selected()
        self.assertEqual(self.editor.toPlainText(), SAMPLE)
        self.assertIn("变化", self.view.hint.text())

    def test_paragraph_enter_is_visible_and_save_includes_live_content(self):
        self.structure()
        block = self.select("text")
        before_cursor = self.editor.textCursor().position()
        with patch.object(self.window.compile, "compile_current") as compile_call:
            self.view.edit_selected()
            local = self.view.local_editor
            local.text.setPlainText("第一行😀\n第二行 & 百分比 50%")
            self.assertIn("第一行😀\\\\\n第二行 \\& 百分比 50\\%", self.editor.toPlainText())
            self.assertIn("第一行😀\n第二行", local.preview.toPlainText())
            self.assertTrue(self.window.save_current())
            self.assertEqual(self.file.read_text(), self.editor.toPlainText())
            self.assertEqual(self.editor.textCursor().position(), before_cursor)
            compile_call.assert_not_called()
        self.assertTrue(self.editor.toPlainText().startswith(SAMPLE[:block.start]))
        self.settle()
        self.assertIs(self.view.content_stack.currentWidget(), local)

    def test_table_live_delegate_updates_source_before_focus_loss(self):
        self.structure()
        self.select("table")
        self.view.edit_selected()
        local = self.view.local_editor
        self.assertTrue(local.is_table)
        table = local.table
        table.editItem(table.item(0, 0))
        line = table.findChild(QLineEdit)
        self.assertIsNotNone(line)
        line.selectAll()
        QTest.keyClicks(line, "new & 10%")
        self.assertIn(r"new \& 10\% & b \\ c & d", self.editor.toPlainText())
        self.assertTrue(self.window.save_current())
        self.assertEqual(self.file.read_text(), self.editor.toPlainText())
        # Later cells still point at their own source after length changes.
        local.edit_cell(1, 1, "last")
        self.assertIn(r"c & last\end{tabular}", self.editor.toPlainText())
        self.assertIn("new & 10%", local.preview.toPlainText())

    def test_table_paste_and_clear_use_one_undo_transaction(self):
        self.structure()
        self.select("table")
        self.view.edit_selected()
        local = self.view.local_editor
        local.table.setCurrentCell(0, 0)
        local.paste_cells("one\ttwo\nthree\tfour")
        self.assertIn(r"one & two \\ three & four", self.editor.toPlainText())
        self.view.undo_source()
        self.assertEqual(self.editor.toPlainText(), SAMPLE)

    def test_tab_switch_or_conflict_rejects_live_local_edit(self):
        self.structure()
        self.select("text")
        self.view.edit_selected()
        self.window.current_tab().external_conflict = True
        self.view.local_editor.text.setPlainText("must not overwrite")
        self.assertEqual(self.editor.toPlainText(), SAMPLE)
        self.assertIn("冲突", self.view.hint.text())
        self.window.current_tab().external_conflict = False
        self.view.edit_selected()
        self.window.new_document()
        self.view.local_editor.text.setPlainText("must not switch targets")
        self.assertEqual(self.editor.toPlainText(), SAMPLE)

    def test_breadcrumb_shows_full_ancestry(self):
        self.structure()
        self.select("table")
        self.assertEqual(self.view.breadcrumb.text(), "main.tex › 方法 › 数据 › 表格")
        self.assertNotIn("a b", self.view.breadcrumb.text())

    def test_breadcrumb_ends_at_kind_not_content_and_resets_on_tab_change(self):
        self.structure()
        for kind, label in (("text", "正文"), ("formula", "公式"), ("title", "文稿标题"), ("raw", "自定义 LaTeX")):
            self.select(kind)
            self.assertEqual(self.view.breadcrumb._parts[-1], label)
        self.window.new_document()
        self.settle()
        self.assertNotIn("main.tex", self.view.breadcrumb.text())

    def test_breadcrumb_keeps_full_accessible_path_when_visually_elided(self):
        from app.gui.structure_view import StructureBreadcrumb
        path = StructureBreadcrumb()
        try:
            path.set_path(("很长的文件名称.tex", "很长的章标题", "另一层标题", "数据处理", "表格"))
            path.resize(180, path.sizeHint().height())
            labels, gap = path._visible_parts()
            self.assertEqual(labels[-1][0], "表格")
            self.assertLessEqual(sum(width for _, width in labels) + gap * (len(labels) - 1), path.width())
            self.assertIn("很长的章标题", path.toolTip())
            self.assertIn("数据处理", path.accessibleName())
            self.assertEqual(path.minimumSizeHint().width(), 0)
            self.assertFalse(path.grab().isNull())
        finally:
            path.deleteLater()

    def test_complex_table_stays_local_without_lossy_conversion(self):
        text = r"\begin{tabular}{ll}\multicolumn{2}{c}{merged} \\ a & b\end{tabular}"
        self.editor.setPlainText(text)
        self.structure()
        self.select("table")
        self.view.edit_selected()
        self.assertFalse(self.view.local_editor.is_table)
        self.assertTrue(self.view.active)
        self.assertIn("合并单元格", self.view.local_editor.help.text())
        self.assertEqual(self.editor.toPlainText(), text)

    def test_local_preedit_does_not_modify_source_before_commit(self):
        from PySide6.QtGui import QInputMethodEvent
        from PySide6.QtWidgets import QApplication
        self.structure()
        self.select("text")
        self.view.edit_selected()
        local = self.view.local_editor.text
        QApplication.sendEvent(local, QInputMethodEvent("ceshi", []))
        self.assertEqual(self.editor.toPlainText(), SAMPLE)
        commit = QInputMethodEvent()
        commit.setCommitString("测试😀")
        QApplication.sendEvent(local, commit)
        self.assertIn("测试😀", self.editor.toPlainText())
        self.assertNotIn("ceshi", self.editor.toPlainText())

    def test_delete_section_confirmed_and_undo(self):
        self.structure()
        section = self.select("section")
        with patch.object(QMessageBox, "exec"), patch.object(QMessageBox, "clickedButton", lambda box: next(
                b for b in box.buttons() if box.buttonRole(b) == QMessageBox.ButtonRole.DestructiveRole)):
            self.view.delete_selected()
        self.assertEqual(self.editor.toPlainText(), SAMPLE[:section.start] + SAMPLE[section.end:])
        self.view.undo_source()
        self.assertEqual(self.editor.toPlainText(), SAMPLE)

    def table_options(self, source=None):
        if source:
            self.editor.setPlainText(source)
        self.structure()
        self.select("table")
        self.view.edit_selected()
        return self.view.local_editor

    def test_table_dimensions_keep_cells_and_support_source_undo(self):
        local = self.table_options()
        original = self.editor.toPlainText()
        local.table_options.rows_spin.setValue(3)
        self.assertEqual(local.table.rowCount(), 4)
        self.assertEqual(local.table.item(1, 1).text(), "d")
        local.table_options.columns_spin.setValue(3)
        self.assertEqual(local.table.columnCount(), 3)
        local.edit_cell(3, 2, "new cell😀")
        self.assertIn("new cell😀", self.editor.toPlainText())
        self.assertTrue(self.window.save_current())
        self.assertEqual(self.file.read_text(), self.editor.toPlainText())
        self.view.undo_source()
        self.view.undo_source()
        self.view.undo_source()
        self.assertEqual(self.editor.toPlainText(), original)

    def test_table_shrink_cancel_and_confirm_preserve_undo(self):
        local = self.table_options()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            local.table_options.columns_spin.setValue(1)
        self.assertEqual(self.editor.toPlainText(), SAMPLE)
        self.assertEqual(local.table_options.columns_spin.value(), 2)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            local.table_options.columns_spin.setValue(1)
        self.assertEqual(local.table.columnCount(), 1)
        self.assertEqual(local.table.item(1, 0).text(), "c")
        self.view.undo_source()
        self.assertEqual(self.editor.toPlainText(), SAMPLE)

    def test_specs_after_live_cell_edit_use_current_values(self):
        local = self.table_options()
        local.edit_cell(0, 0, "edited😀")
        local.table_options.rows_spin.setValue(4)
        self.assertEqual(local.table.item(0, 0).text(), "edited😀")
        self.assertIn("edited😀", self.editor.toPlainText())
        local.table_options.alignment_combo.setCurrentIndex(local.table_options.alignment_combo.findData("r"))
        self.assertIn("{rr}", self.editor.toPlainText())

    def test_spec_metadata_plain_typing_and_required_package_are_saved(self):
        from app.core.latex_insertions import TableSpec, table_snippet
        source = "\\documentclass{article}\n\\begin{document}\n" + table_snippet(TableSpec(use_booktabs=False)) + "\n\\end{document}"
        local = self.table_options(source)
        local.table_options.booktabs_check.setChecked(True)
        self.assertIn(r"\usepackage{booktabs}", self.editor.toPlainText())
        local.table_options.details_button.setChecked(True)
        field = local.table_options.caption_edit
        QTest.keyClicks(field, "50% & result")
        self.assertIn(r"\caption{50\% \& result}", self.editor.toPlainText())
        self.assertEqual(field.text(), "50% & result")
        label = local.table_options.label_edit
        label.setText("tab:测试")
        self.assertTrue(label.hasAcceptableInput())
        label.textEdited.emit(label.text())
        self.assertIn(r"\label{tab:测试}", self.editor.toPlainText())
        self.assertTrue(self.window.save_current())
        self.assertEqual(self.file.read_text(), self.editor.toPlainText())

    def test_stale_shrink_confirmation_cannot_write(self):
        local = self.table_options()
        def stale(*args):
            self.editor.insertPlainText("changed")
            self.editor.undo()
            return QMessageBox.StandardButton.Yes
        with patch.object(QMessageBox, "question", side_effect=stale):
            local.table_options.columns_spin.setValue(1)
        self.assertEqual(self.editor.toPlainText(), SAMPLE)

    def test_commented_table_keeps_cell_edit_but_disables_specs(self):
        local = self.table_options(SAMPLE.replace(r"\begin{tabular}{ll}", "\\begin{tabular}{ll}\n% keep\n"))
        self.assertTrue(local.is_table)
        self.assertFalse(local.table_options.isEnabled())
        local.edit_cell(0, 0, "safe")
        self.assertIn("% keep", self.editor.toPlainText())
        self.assertIn("safe", self.editor.toPlainText())
