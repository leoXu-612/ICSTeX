"""Insertion-tool orchestration: figures, tables, hyperlinks, equations, lists,
citations, references, image drops, and bib-file mutations.

Each public method maps to a former ``MainWindow`` slot. The controller keeps a
back-reference to the host window because almost every action ends with a
status-bar message, a project-panel refresh, or a snippet insertion that needs
the active editor.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QDialog, QMessageBox

from app.core.formula_input import FinalTextEditPlan, parse_document_selection
from app.core.image_assets import copy_image_atomic
from app.core.latex_insertions import (
    FIGURE_PACKAGES,
    HYPERLINK_PACKAGES,
    SIDE_BY_SIDE_FIGURE_PACKAGES,
    TABLE_PACKAGES,
    FigureSpec,
    HyperlinkSpec,
    SideBySideFigureSpec,
    figure_snippet,
    hyperlink_snippet,
    latex_relative_path,
    package_update,
    sanitize_asset_filename,
    side_by_side_figure_snippet,
    table_snippet,
    unique_asset_path,
)
from app.core.project_tools import (
    append_bib_entry,
    append_bib_import,
    bib_import_from_text,
    fetch_bib_online,
    citation_snippet,
    reference_snippet,
)
from app.core.text_encoding import write_latex_text_atomic
from app.gui import bib_helpers
from app.gui.formula_dialog import FormulaDialog
from app.gui.insert_panel import (
    FigureDialog,
    HyperlinkDialog,
    SideBySideFigureDialog,
    TableDialog,
)
from app.gui.latex_editor import LaTeXEditor
from app.gui.main_window_support import EditorTab
from app.gui.project_panels import BibEntryDialog, BibImportDialog

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.gui.main_window import MainWindow


class InsertionActions:
    def __init__(self, window: "MainWindow") -> None:
        self.window = window

    # --- bibliography -------------------------------------------------------

    def add_reference(self) -> None:
        window = self.window
        tab = window._require_saved_tab_for_assets()
        if tab is None:
            return
        dialog = BibEntryDialog(window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values.key and not values.title:
            QMessageBox.warning(window, "引用信息不完整", "请至少填写 Bib key 或标题。")
            return

        bib_file = bib_helpers.bib_file_for_tab(tab, create=True)
        assert bib_file is not None
        try:
            old_text = bib_file.read_text(encoding="utf-8") if bib_file.exists() else ""
            write_latex_text_atomic(bib_file, append_bib_entry(old_text, values), encoding="utf-8")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(window, "引用保存失败", str(exc))
            return
        bib_helpers.ensure_bibliography_block(tab)
        window.refresh_project_panels()
        window.statusBar().showMessage(f"已添加引用到 {bib_file.name}。", 4000)

    def import_reference(self) -> None:
        window = self.window
        tab = window._require_saved_tab_for_assets()
        if tab is None:
            return
        dialog = BibImportDialog(window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        result = None
        if dialog.online():
            try:
                result = fetch_bib_online(dialog.text())
            except OSError as exc:
                QMessageBox.warning(window, "联网获取失败", f"{exc}\n将改用离线 BibTeX 骨架。")
        if result is None:
            try:
                result = bib_import_from_text(dialog.text())
            except ValueError as exc:
                QMessageBox.warning(window, "引用导入失败", str(exc))
                return

        bib_file = bib_helpers.bib_file_for_tab(tab, create=True)
        assert bib_file is not None
        try:
            old_text = bib_file.read_text(encoding="utf-8") if bib_file.exists() else ""
            write_latex_text_atomic(bib_file, append_bib_import(old_text, result), encoding="utf-8")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(window, "引用保存失败", str(exc))
            return
        bib_helpers.ensure_bibliography_block(tab)
        window.refresh_project_panels()
        window.statusBar().showMessage(f"已导入 {result.source} 引用：{result.key}", 4000)

    # --- citations / references --------------------------------------------

    def insert_citation(self, key: str) -> None:
        window = self.window
        tab = window._ensure_editable_tab()
        if tab is None:
            return
        self.insert_snippet(tab, citation_snippet(key), (), "已插入 citation。", block=False)
        if tab.path:
            bib_helpers.ensure_bibliography_block(tab)
        window.refresh_project_panels()

    def insert_reference(self, label: str, command: str) -> None:
        window = self.window
        tab = window._ensure_editable_tab()
        if tab is None:
            return
        packages: tuple[str, ...] = ()
        if command == "autoref":
            packages = HYPERLINK_PACKAGES
        elif command == "eqref":
            packages = ("amsmath",)
        self.insert_snippet(tab, reference_snippet(label, command), packages, "已插入引用。", block=False)
        window.refresh_project_panels()

    # --- figures / tables / equations / lists ------------------------------

    def insert_existing_image(self, relative_path: str) -> None:
        window = self.window
        tab = window._ensure_editable_tab()
        if tab is None:
            return
        label = f"fig:{Path(relative_path).stem.replace(' ', '_')}"
        self.insert_snippet(
            tab,
            figure_snippet(FigureSpec(image_path=relative_path, label=label)),
            FIGURE_PACKAGES,
            "已从图片资源插入 figure。",
        )
        window.refresh_project_panels()

    def insert_dropped_images(self, image_paths: list[str]) -> None:
        window = self.window
        sender = window.sender()
        tab = window.tabs.get(id(sender)) if isinstance(sender, LaTeXEditor) else window.current_tab()
        if tab is None:
            return
        if tab.path is None:
            QMessageBox.information(window, "请先保存", "请先保存当前 LaTeX 文件，再拖入图片。")
            return

        snippets: list[str] = []
        for image_path in image_paths:
            relative_path = self.copy_image_asset(tab, image_path)
            if relative_path is None:
                continue
            snippets.append(
                figure_snippet(
                    FigureSpec(
                        image_path=relative_path,
                        caption=self._default_figure_caption(relative_path),
                        label=self._default_figure_label(relative_path),
                    )
                )
            )

        if not snippets:
            return
        self.insert_snippet(
            tab,
            "\n\n".join(snippets),
            FIGURE_PACKAGES,
            f"已拖入 {len(snippets)} 张图片并生成 figure。",
        )
        window.refresh_project_panels()

    def insert_figure(self) -> None:
        window = self.window
        tab = window._require_saved_tab_for_assets()
        if tab is None:
            return
        dialog = FigureDialog(window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        image_path = self.copy_image_asset(tab, values.image_path)
        if image_path is None:
            return
        spec = FigureSpec(
            image_path=image_path,
            width=values.width,
            caption=values.caption,
            label=values.label,
            placement=values.placement,
        )
        self.insert_snippet(
            tab,
            figure_snippet(spec),
            self._packages_for_placement(FIGURE_PACKAGES, spec.placement),
            "已插入图片。",
        )

    def insert_side_by_side_figures(self) -> None:
        window = self.window
        tab = window._require_saved_tab_for_assets()
        if tab is None:
            return
        dialog = SideBySideFigureDialog(window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        left_path = self.copy_image_asset(tab, values.left_image_path)
        if left_path is None:
            return
        right_path = self.copy_image_asset(tab, values.right_image_path)
        if right_path is None:
            return
        spec = SideBySideFigureSpec(
            left_image_path=left_path,
            right_image_path=right_path,
            left_caption=values.left_caption,
            right_caption=values.right_caption,
            caption=values.caption,
            label=values.label,
            width=values.width,
            placement=values.placement,
        )
        self.insert_snippet(
            tab,
            side_by_side_figure_snippet(spec),
            self._packages_for_placement(SIDE_BY_SIDE_FIGURE_PACKAGES, spec.placement),
            "已插入并排图片。",
        )

    def insert_table(self) -> None:
        window = self.window
        tab = window._ensure_editable_tab()
        if tab is None:
            return
        dialog = TableDialog(window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self.insert_snippet(
            tab,
            table_snippet(values),
            self._packages_for_placement(TABLE_PACKAGES, values.placement),
            "已插入表格。",
        )

    def insert_hyperlink(self) -> None:
        window = self.window
        tab = window._ensure_editable_tab()
        if tab is None:
            return
        dialog = HyperlinkDialog(window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not values.text or not values.url:
            QMessageBox.warning(window, "超链接信息不完整", "请同时填写显示文本和 URL。")
            return
        self.insert_snippet(
            tab,
            hyperlink_snippet(HyperlinkSpec(text=values.text, url=values.url)),
            HYPERLINK_PACKAGES,
            "已插入超链接。",
            block=False,
        )

    def insert_equation(self) -> None:
        window = self.window
        tab = window._ensure_editable_tab()
        if tab is None:
            return
        snippet = "\\begin{equation}\n  \n\\end{equation}"
        self.insert_snippet(
            tab,
            snippet,
            ("amsmath",),
            "已插入公式。",
            cursor_offset=len("\\begin{equation}\n  "),
        )

    def open_formula_composer(self) -> None:
        """Open the formula composer for an exact formula selection.

        With no selection, the composer opens in insertion mode seeded with an
        empty ``equation`` draft and inserts the composed formula at the
        cursor on apply. A selection that is not exactly one supported formula
        wrapper is left untouched (source mode): the composer never guesses a
        replacement range.
        """

        window = self.window
        tab = window._ensure_editable_tab()
        if tab is None:
            return
        editor = tab.editor
        cursor = editor.textCursor()
        document = editor.toPlainText()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        if start == end:
            dialog = FormulaDialog(
                window,
                document,
                start,
                end,
                seed_text=r"\begin{equation}\end{equation}",
            )
        else:
            if parse_document_selection(document, start, end) is None:
                QMessageBox.information(
                    window,
                    "编辑公式",
                    "请先选中一个完整公式（$…$、\\(…\\)、\\[…\\]、equation 或 equation*）。\n"
                    "原选区保持不变。",
                )
                return
            dialog = FormulaDialog(window, document, start, end)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        plan = dialog.plan()
        if plan is None:
            return
        if self.apply_formula_plan(tab, plan):
            window.refresh_project_panels()
            window.statusBar().showMessage("已应用公式编辑。", 4000)

    def apply_formula_plan(self, tab: EditorTab, plan: FinalTextEditPlan) -> bool:
        """Apply a formula edit plan with a revision guard and one Undo step.

        The current selection must still be exactly the original formula
        envelope; otherwise the edit is refused so a stale plan can never
        overwrite newer document content. Package insertion and the formula
        replacement are merged into one Undo step.
        """

        window = self.window
        editor = tab.editor
        current = editor.toPlainText()
        if current[plan.start : plan.end] != plan.source_text:
            QMessageBox.warning(
                window,
                "编辑公式",
                "文档在公式编辑期间已变化，已取消替换，避免覆盖新内容。",
            )
            return False

        update = None
        inserted_text = ""
        if plan.packages:
            update = package_update(current, plan.packages)
            inserted_text = update.inserted_text
            if update.insert_position < plan.end and update.insert_position >= plan.start:
                QMessageBox.warning(
                    window,
                    "编辑公式",
                    "package 插入位置与公式选区重叠，已取消应用以保护正文。",
                )
                return False

        cursor = editor.textCursor()
        cursor.beginEditBlock()
        try:
            if inserted_text:
                package_cursor = editor.textCursor()
                package_cursor.setPosition(update.insert_position)
                package_cursor.insertText(inserted_text)

            shift = len(inserted_text) if update is not None and update.insert_position <= plan.start else 0
            new_start = plan.start + shift
            new_end = plan.end + shift
            replace_cursor = editor.textCursor()
            replace_cursor.setPosition(new_start)
            replace_cursor.setPosition(new_end, QTextCursor.MoveMode.KeepAnchor)
            replace_cursor.insertText(plan.text)

            final_cursor = editor.textCursor()
            if plan.cursor_offset is not None:
                final_cursor.setPosition(new_start + plan.cursor_offset)
            else:
                final_cursor.setPosition(new_start + len(plan.text))
            editor.setTextCursor(final_cursor)
        finally:
            cursor.endEditBlock()

        window.apply_editor_options(editor)
        editor.ensureCursorVisible()
        editor.setFocus()
        return True

    def insert_list(self) -> None:
        window = self.window
        tab = window._ensure_editable_tab()
        if tab is None:
            return
        snippet = "\\begin{itemize}\n  \\item \n\\end{itemize}"
        self.insert_snippet(
            tab,
            snippet,
            (),
            "已插入列表。",
            cursor_offset=len("\\begin{itemize}\n  \\item "),
        )

    def insert_section(self) -> None:
        window = self.window
        tab = window._ensure_editable_tab()
        if tab is None:
            return
        snippet = "\\section{Section Title}\n"
        self.insert_snippet(
            tab,
            snippet,
            (),
            "已插入章节标题。",
            cursor_offset=len("\\section{"),
        )

    def insert_cases(self) -> None:
        window = self.window
        tab = window._ensure_editable_tab()
        if tab is None:
            return
        snippet = "\\[\nf(x)=\\begin{cases}\n  0, & x < 0 \\\\\n  1, & x \\ge 0\n\\end{cases}\n\\]"
        self.insert_snippet(
            tab,
            snippet,
            ("amsmath",),
            "已插入分段函数。",
            cursor_offset=len("\\[\nf(x)=\\begin{cases}\n  "),
        )

    def insert_quote(self) -> None:
        window = self.window
        tab = window._ensure_editable_tab()
        if tab is None:
            return
        snippet = "\\begin{quote}\n  Quoted text.\n\\end{quote}"
        self.insert_snippet(
            tab,
            snippet,
            (),
            "已插入引用块。",
            cursor_offset=len("\\begin{quote}\n  "),
        )

    # --- history snapshot restore ------------------------------------------

    def restore_history_snapshot(self, snapshot_path: str) -> None:
        window = self.window
        tab = window.current_tab()
        if tab is None:
            return
        path = Path(snapshot_path)
        if not path.exists():
            QMessageBox.warning(window, "快照不存在", f"找不到这个历史快照：\n{path}")
            window.refresh_project_panels()
            return
        choice = QMessageBox.question(
            window,
            "恢复历史版本",
            "将这个历史版本恢复到当前编辑器？当前内容会变为未保存修改。",
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            QMessageBox.warning(window, "恢复失败", str(exc))
            return
        tab.editor.blockSignals(True)
        try:
            tab.editor.setPlainText(text)
        finally:
            tab.editor.blockSignals(False)
        window.apply_editor_options(tab.editor)
        tab.modified = True
        tab.dirty = True
        window._mark_source_edited(tab)
        if tab is window.current_tab():
            window._update_pdf_action_state()
        window._set_tab_title(tab)
        window.refresh_project_panels()
        window.statusBar().showMessage("已恢复历史版本，请确认后保存。", 5000)

    # --- internal helpers --------------------------------------------------

    def copy_image_asset(self, tab: EditorTab, image_name: str) -> str | None:
        window = self.window
        if tab.path is None:
            return None
        source = Path(image_name).expanduser()
        if not source.is_file():
            QMessageBox.warning(window, "找不到图片", "请选择一个存在的图片文件。")
            return None

        figures_dir = tab.path.parent / "figures"
        figures_dir.mkdir(parents=True, exist_ok=True)
        safe_name = sanitize_asset_filename(source.name)
        destination = figures_dir / safe_name
        if source.resolve() != destination.resolve():
            destination = unique_asset_path(figures_dir, safe_name)
            try:
                copy_image_atomic(source, destination)
            except OSError as exc:
                QMessageBox.warning(window, "图片复制失败", str(exc))
                return None
        return latex_relative_path(tab.path, destination)

    def insert_snippet(
        self,
        tab: EditorTab,
        snippet: str,
        packages: tuple[str, ...],
        message: str,
        *,
        cursor_offset: int | None = None,
        block: bool = True,
    ) -> None:
        self.ensure_packages(tab, packages)
        self.window.apply_editor_options(tab.editor)
        text = snippet
        adjusted_offset = cursor_offset
        if block:
            prefix, suffix = self._block_padding(tab.editor)
            text = f"{prefix}{snippet}{suffix}"
            if adjusted_offset is not None:
                adjusted_offset += len(prefix)
        tab.editor.insert_latex_snippet(text, adjusted_offset)
        self.window.apply_editor_options(tab.editor)
        tab.editor.ensureCursorVisible()
        tab.editor.setFocus()
        self.window.statusBar().showMessage(message, 4000)

    def ensure_packages(self, tab: EditorTab, packages: tuple[str, ...]) -> None:
        if not packages:
            return
        editor = tab.editor
        cursor = editor.textCursor()
        old_text = editor.toPlainText()
        update = package_update(old_text, packages)
        if update.text == old_text:
            return

        old_position = cursor.position()
        editor.setPlainText(update.text)
        self.window.apply_editor_options(editor)
        new_position = old_position
        if old_position >= update.insert_position:
            new_position += len(update.inserted_text)
        cursor = editor.textCursor()
        cursor.setPosition(min(new_position, len(update.text)))
        editor.setTextCursor(cursor)

    @staticmethod
    def _block_padding(editor: LaTeXEditor) -> tuple[str, str]:
        text = editor.toPlainText()
        cursor_position = editor.textCursor().position()
        prefix = "" if cursor_position == 0 or text[cursor_position - 1] == "\n" else "\n"
        suffix = "" if cursor_position >= len(text) or text[cursor_position : cursor_position + 1] == "\n" else "\n"
        return prefix, suffix

    @staticmethod
    def _packages_for_placement(packages: tuple[str, ...], placement: str) -> tuple[str, ...]:
        if placement == "H" and "float" not in packages:
            return (*packages, "float")
        return packages

    @staticmethod
    def _default_figure_caption(relative_path: str) -> str:
        stem = Path(relative_path).stem.replace("_", " ").replace("-", " ").strip()
        return stem or "image"

    @staticmethod
    def _default_figure_label(relative_path: str) -> str:
        safe_name = sanitize_asset_filename(Path(relative_path).name)
        stem = Path(safe_name).stem.replace(".", "_")
        return f"fig:{stem or 'image'}"
