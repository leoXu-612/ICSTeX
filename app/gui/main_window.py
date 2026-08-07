from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from PySide6.QtCore import QModelIndex, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QWidget,
)

from app import __app_name__
from app.core.compiler import BuildPurpose, CompileManager, CompileOutcome, CompileResult
from app.core.logging_config import configure_logging
from app.core.diagnostics import Diagnostic
from app.core.environment_doctor import FeedbackMetadata, build_environment_report, build_feedback_bundle
from app.core.file_watcher import ExternalFileWatcher
from app.core.latex_insertions import (
    export_template,
    import_custom_template,
    save_custom_template,
    template_for_key,
)
from app.core.latex_tools import LaTeXEngine, LaTeXToolchain, detect_toolchain
from app.core.log_parser import LaTeXError
from app.core.paths import (
    find_root_tex,
    latex_dependency_closure,
    normalize_path,
    resolve_root_tex,
)
from app.core.pdf_state import (
    FRESHNESS_LABELS,
    FRESHNESS_SEVERITY,
    PdfBuildRecord,
    PdfFreshness,
    PdfStateStore,
)
from app.core.preview_state import (
    FRESHNESS_LABELS as PREVIEW_FRESHNESS_LABELS,
    FRESHNESS_SEVERITY as PREVIEW_FRESHNESS_SEVERITY,
    PreviewFreshness,
    PreviewStateStore,
)
from app.core.project_tools import initialize_project
from app.core.synctex import pdf_to_source, source_to_pdf
from app.core.settings import AppPreferences, AppSettings
from app.core.text_encoding import DecodedLatexText, LatexTextDecodeError, decode_latex_bytes
from app.core.word_count import count_project, count_text
from app.gui.assets import app_cover_path
from app.gui.environment_doctor_dialog import EnvironmentDoctorDialog, FeedbackContext
from app.gui import bib_helpers
from app.gui import editor_view_state as view_state
from app.gui.compile_controller import CompileController
from app.gui.document_lifecycle import DocumentLifecycle
from app.gui.editor_tab_manager import EditorTabManager
from app.gui.insertion_actions import InsertionActions
from app.gui.preferences_controller import PreferencesController
from app.gui.pdf_export_controller import PdfExportController
from app.gui.project_panel_controller import ProjectPanelController
from app.gui.latex_editor import LaTeXEditor
from app.gui.log_bridge import QtLogBridge
from app.gui.main_window_layout import build_ui
from app.gui.main_window_signals import connect_signals
from app.gui.main_window_support import (
    CompileSignals,
    DisplayedPdf,
    EditorTab,
    EditorViewState,
    SAMPLE_DOCUMENT,
    set_dynamic_property,
)
from app.gui.project_panels import ProjectWizardDialog
from app.gui.theme import apply_theme
from app.gui.user_guide import UserGuideDialog


_SOURCE_ENCODING_CHOICES = (
    ("简体中文（GB18030）", "gb18030"),
    ("Windows 西文（CP1252）", "cp1252"),
    ("Latin-1（ISO-8859-1）", "iso-8859-1"),
    ("繁体中文（Big5）", "big5"),
    ("日文（Shift_JIS）", "shift_jis"),
    ("Mac Roman", "mac_roman"),
)


class MainWindow(QMainWindow):
    def __init__(self, settings_store: AppSettings | None = None) -> None:
        super().__init__()
        self.setWindowTitle(__app_name__)
        cover_path = app_cover_path()
        if cover_path.exists():
            self.setWindowIcon(QIcon(str(cover_path)))
        self.resize(1440, 900)
        self.setMinimumSize(1080, 720)
        self.app_settings = settings_store or AppSettings()
        self.preferences = self.app_settings.load_preferences()
        self.toolchain: LaTeXToolchain = detect_toolchain()
        self.current_engine = self.preferences.default_engine
        self.signals = CompileSignals()
        self.tabs: dict[int, EditorTab] = {}
        self.pdf_state = PdfStateStore()
        self.preview_state = PreviewStateStore()
        self.displayed_pdfs: dict[Path, DisplayedPdf] = {}
        self.preview_asset_roots: dict[Path, set[Path]] = {}
        self.preview_root_assets: dict[Path, set[Path]] = {}
        self.compile_managers: dict[Path, CompileManager] = {}
        self.compile_build_owners: dict[tuple[Path, int], CompileManager] = {}
        self.compile_active_builds: dict[
            Path, tuple[CompileManager, int, BuildPurpose]
        ] = {}
        self.compile_purposes: dict[tuple[Path, int], BuildPurpose] = {}
        self.compile_start_times: dict[Path, float] = {}
        self.compile_start_purposes: dict[Path, BuildPurpose] = {}
        self._include_cache: dict[Path, frozenset[Path]] = {}
        self.file_watcher = ExternalFileWatcher(lambda path: self.signals.external_changed.emit(str(path)))
        self.local_save_contents: dict[Path, str] = {}
        self.save_debounce_ms = self.preferences.save_debounce_ms
        self.compile_debounce_ms = self.preferences.compile_debounce_ms
        self.compile_started_at: float | None = None
        self.documents = DocumentLifecycle(self)
        self.tab_manager = EditorTabManager(self)
        self.compile = CompileController(self)
        self.pdf_export = PdfExportController(self)
        self.insertions = InsertionActions(self)
        self.project_panels = ProjectPanelController(self)
        self.preferences_controller = PreferencesController(self)

        self._build_ui()
        saved_window_state = self.app_settings.settings.value("window/block_console_state")
        if saved_window_state:
            self.restoreState(saved_window_state)
        self._connect_signals()
        self._update_pdf_action_state()
        self.update_document_view_state()
        self.update_welcome_page()
        self._show_toolchain_status()

    def _build_ui(self) -> None:
        build_ui(self)

    def _connect_signals(self) -> None:
        connect_signals(self)

    def set_toolbox_visible(self, visible: bool) -> None:
        self.preferences_controller.set_toolbox_visible(visible)

    def sync_toolbox_action(self, visible: bool) -> None:
        self.preferences_controller.sync_toolbox_action(visible)

    def sync_auto_compile_action(self, enabled: bool) -> None:
        self.preferences_controller.sync_auto_compile_action(enabled)

    def sync_auto_compile_toggle(self, enabled: bool) -> None:
        self.preferences_controller.sync_auto_compile_toggle(enabled)

    def new_document(self) -> None:
        editor = self._make_editor(SAMPLE_DOCUMENT)
        self._add_tab(EditorTab(editor=editor), "未命名.tex")
        self.refresh_project_panels()

    def new_project(self) -> None:
        dialog = ProjectWizardDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            project = initialize_project(dialog.values())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "项目创建失败", str(exc))
            return
        self.tree.setRootIndex(self.model.index(str(project.root_dir)))
        self._remember_recent_project(project.root_dir)
        self.open_file(project.tex_file)
        self.sidebar_tabs.setCurrentIndex(0)
        self.statusBar().showMessage(f"已创建项目：{project.root_dir.name}", 5000)

    def new_document_from_template(self, key: str) -> None:
        template = template_for_key(key)
        editor = self._make_editor(template.text)
        self._add_tab(EditorTab(editor=editor), template.filename)
        self.statusBar().showMessage(f"已创建模板：{template.title}", 4000)
        self.refresh_project_panels()

    def save_current_as_template(self) -> None:
        tab = self.current_tab()
        if tab is None:
            QMessageBox.information(self, "保存模板", "请先打开或新建一个文档。")
            return
        default_title = tab.path.stem if tab.path else "My Template"
        title, ok = QInputDialog.getText(self, "保存当前为模板", "模板名称：", text=default_title)
        if not ok:
            return
        try:
            template = save_custom_template(title, tab.editor.toPlainText())
        except OSError as exc:
            QMessageBox.warning(self, "保存模板失败", str(exc))
            return
        self.templates_panel.refresh_templates()
        self.statusBar().showMessage(f"已保存个人模板：{template.title}", 5000)

    def import_template_dialog(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "导入 .tex 模板", str(Path.home()), "LaTeX 模板 (*.tex)")
        if not file_name:
            return
        try:
            template = import_custom_template(Path(file_name).expanduser())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "导入模板失败", str(exc))
            return
        self.templates_panel.refresh_templates()
        self.statusBar().showMessage(f"已导入个人模板：{template.title}", 5000)

    def export_template_dialog(self, key: str) -> None:
        try:
            template = template_for_key(key)
        except ValueError as exc:
            QMessageBox.warning(self, "导出模板失败", str(exc))
            return
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "导出模板",
            str(Path.home() / template.filename),
            "LaTeX 模板 (*.tex)",
        )
        if not file_name:
            return
        try:
            target = export_template(key, Path(file_name).expanduser())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "导出模板失败", str(exc))
            return
        self.statusBar().showMessage(f"已导出模板：{target}", 5000)

    def add_reference(self) -> None:
        self.insertions.add_reference()

    def import_reference(self) -> None:
        self.insertions.import_reference()

    def insert_citation(self, key: str) -> None:
        self.insertions.insert_citation(key)

    def insert_reference(self, label: str, command: str) -> None:
        self.insertions.insert_reference(label, command)

    def jump_to_outline(self, line: int) -> None:
        self.project_panels.jump_to_outline(line)

    def run_project_search(self, query: str, case_sensitive: bool, whole_word: bool) -> None:
        self.project_panels.run_project_search(query, case_sensitive, whole_word)

    def jump_to_project_search_result(self, path: str, line: int, column: int) -> None:
        self.project_panels.jump_to_project_search_result(path, line, column)

    def insert_existing_image(self, relative_path: str) -> None:
        self.insertions.insert_existing_image(relative_path)

    def insert_dropped_images(self, image_paths: list[str]) -> None:
        self.insertions.insert_dropped_images(image_paths)

    def restore_history_snapshot(self, snapshot_path: str) -> None:
        self.insertions.restore_history_snapshot(snapshot_path)

    def insert_figure(self) -> None:
        self.insertions.insert_figure()

    def insert_side_by_side_figures(self) -> None:
        self.insertions.insert_side_by_side_figures()

    def insert_table(self) -> None:
        self.insertions.insert_table()

    def insert_hyperlink(self) -> None:
        self.insertions.insert_hyperlink()

    def insert_equation(self) -> None:
        self.insertions.insert_equation()

    def open_formula_composer(self) -> None:
        self.insertions.open_formula_composer()

    def show_import_perf_dialog(self) -> None:
        from app.gui.import_perf_dialog import ImportPerfDialog

        ImportPerfDialog(self).exec()

    def show_block_project_dialog(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        from app.core.blocks.project_io import load_block_project
        from app.gui.blocks.project_dialog import BlockProjectDialog

        directory = QFileDialog.getExistingDirectory(self, "选择 Block 项目目录")
        if not directory:
            return
        project = load_block_project(directory)
        BlockProjectDialog(
            project["registry"],
            layout=project["layout"],
            document_theme=project["document_theme"],
            project_dir=project["project_dir"],
        ).exec()

    def insert_list(self) -> None:
        self.insertions.insert_list()

    def insert_section(self) -> None:
        self.insertions.insert_section()

    def insert_cases(self) -> None:
        self.insertions.insert_cases()

    def insert_quote(self) -> None:
        self.insertions.insert_quote()

    def open_file_dialog(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "打开 LaTeX 文件", str(Path.home()), "LaTeX 文件 (*.tex);;所有文件 (*)")
        if file_name:
            self.open_file(Path(file_name))

    def open_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "打开项目文件夹", str(Path.home()))
        if not folder:
            return
        root = Path(folder)
        self.tree.setRootIndex(self.model.index(str(root)))
        self._remember_recent_project(root)
        candidate = find_root_tex(root)
        if candidate:
            self.open_file(candidate)
        else:
            self.statusBar().showMessage(f"已打开文件夹：{root.name}。未自动找到 root .tex。", 5000)

    def open_tree_item(self, index: QModelIndex) -> None:
        path = Path(self.model.filePath(index))
        if path.is_file() and path.suffix.lower() == ".tex":
            self.open_file(path)

    def open_file(self, path: Path, line: int | None = None) -> None:
        path = path.expanduser().resolve()
        for tab_id, tab in self.tabs.items():
            if tab.path == path:
                self.editor_tabs.setCurrentIndex(self._index_for_tab_id(tab_id))
                if line:
                    self._jump_to_line(tab.editor, line)
                return

        try:
            data = path.read_bytes()
        except OSError as exc:
            QMessageBox.warning(self, "打开失败", str(exc))
            return
        decoded = self._decode_source_for_open(path, data)
        if decoded is None:
            return

        editor = self._make_editor(decoded.text)
        tab = EditorTab(editor=editor, path=path, encoding=decoded.encoding)
        self._add_tab(tab, path.name)
        self._watch_file(path)
        self.tree.setRootIndex(self.model.index(str(path.parent)))
        self._remember_recent_file(path)
        if line:
            self._jump_to_line(editor, line)
        self.compile_current(immediate=True)

    def _decode_source_for_open(self, path: Path, data: bytes) -> DecodedLatexText | None:
        try:
            return decode_latex_bytes(data)
        except LatexTextDecodeError as exc:
            labels = [label for label, _encoding in _SOURCE_ENCODING_CHOICES]
            selected, accepted = QInputDialog.getItem(
                self,
                "选择文件编码",
                (
                    f"“{path.name}”无法按 {exc.encoding} 解码。\n"
                    "ICSTeX 不会用替换字符强行打开，以免保存后损坏原文件。\n"
                    "请选择原文件的编码："
                ),
                labels,
                0,
                False,
            )
            if not accepted:
                self.statusBar().showMessage(f"已取消打开：{path.name}", 4000)
                return None
            chosen_encoding = dict(_SOURCE_ENCODING_CHOICES)[selected]
            try:
                return decode_latex_bytes(data, encoding=chosen_encoding)
            except LatexTextDecodeError as selected_error:
                QMessageBox.warning(
                    self,
                    "打开失败",
                    f"“{path.name}”也无法按 {selected_error.encoding} 解码。原文件未被修改。",
                )
                return None

    def save_current(self) -> bool:
        tab = self.current_tab()
        if not tab:
            return False
        if tab.path is None:
            return self.save_current_as()
        return self.flush_pending_save(tab)

    def save_current_as(self) -> bool:
        tab = self.current_tab()
        if not tab:
            return False
        file_name, _ = QFileDialog.getSaveFileName(self, "保存 LaTeX 文件", str(Path.home() / "main.tex"), "LaTeX 文件 (*.tex)")
        if not file_name:
            return False
        path = Path(file_name).expanduser().resolve()
        if path.suffix.lower() != ".tex":
            path = path.with_suffix(".tex")
        self._cancel_save_timer(tab)
        tab.pending_compile_after_save = False
        return self._save_tab(tab, path)

    def _compile_root_for_tab(self, tab: EditorTab | None) -> Path | None:
        if tab is None:
            return None
        if tab.manager is not None:
            return tab.manager.root_file
        if tab.path is None:
            return None
        root_info = resolve_root_tex(tab.path)
        return normalize_path(root_info.root or tab.path)

    def _active_pdf_record(self) -> PdfBuildRecord | None:
        root = self._compile_root_for_tab(self.current_tab())
        return self.pdf_state.record_for(root) if root is not None else None

    def _active_preview_record(self):
        root = self._compile_root_for_tab(self.current_tab())
        return self.preview_state.record_for(root) if root is not None else None

    def _mark_source_edited(self, tab: EditorTab) -> None:
        root = self._compile_root_for_tab(tab)
        if root is not None:
            self.pdf_state.mark_edited(root)
            self.preview_state.mark_edited(root)
        if tab.path is None:
            return
        path = normalize_path(tab.path)
        for record in self.pdf_state.records():
            if record.root_file != path and record.root_file != root:
                if path in self._dependencies_for_root(record.root_file):
                    self.pdf_state.mark_edited(record.root_file)
                    self.preview_state.mark_edited(record.root_file)

    def _dependencies_for_root(self, root: Path) -> frozenset[Path]:
        # Recursive include closure, cached per root; the cache is dropped on
        # every save/external reload because only disk content defines it.
        deps = self._include_cache.get(root)
        if deps is None:
            deps = latex_dependency_closure(root)
            self._include_cache[root] = deps
        return deps

    def _invalidate_include_cache(self) -> None:
        self._include_cache.clear()

    def _select_displayed_pdf(self, root: Path) -> DisplayedPdf | None:
        canonical = self.pdf_state.record_for(root)
        preview = self.preview_state.record_for(root)
        canonical_revision = canonical.last_successful_revision
        preview_revision = preview.last_successful_revision

        if (
            canonical.has_valid_pdf
            and canonical.freshness is PdfFreshness.CURRENT
            and canonical_revision is not None
        ):
            assert canonical.last_successful_pdf is not None
            return DisplayedPdf(root, BuildPurpose.FINAL, canonical_revision, canonical.last_successful_pdf)
        if (
            preview.has_valid_pdf
            and preview.freshness is PreviewFreshness.CURRENT
            and preview_revision is not None
        ):
            assert preview.last_successful_pdf is not None
            return DisplayedPdf(root, BuildPurpose.PREVIEW, preview_revision, preview.last_successful_pdf)

        candidates: list[DisplayedPdf] = []
        if canonical.has_valid_pdf and canonical_revision is not None:
            assert canonical.last_successful_pdf is not None
            candidates.append(
                DisplayedPdf(root, BuildPurpose.FINAL, canonical_revision, canonical.last_successful_pdf)
            )
        if preview.has_valid_pdf and preview_revision is not None:
            assert preview.last_successful_pdf is not None
            candidates.append(
                DisplayedPdf(root, BuildPurpose.PREVIEW, preview_revision, preview.last_successful_pdf)
            )
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (item.revision, item.purpose is BuildPurpose.FINAL),
        )

    def _sync_pdf_panel_to_active_root(self) -> None:
        root = self._compile_root_for_tab(self.current_tab())
        displayed = self._select_displayed_pdf(root) if root is not None else None
        if displayed is not None:
            previous = self.displayed_pdfs.get(displayed.root_file)
            needs_reload = (
                self.pdf_panel.current_pdf != displayed.path
                or self.pdf_panel.current_logical_key != displayed.root_file
                or previous != displayed
            )
            self.displayed_pdfs[displayed.root_file] = displayed
            if needs_reload:
                self.pdf_panel.load_pdf(displayed.path, logical_key=displayed.root_file)
        else:
            if root is not None:
                self.displayed_pdfs.pop(root, None)
            self.pdf_panel.clear_pdf()
        self._update_pdf_action_state()

    def _compiled_pdf_path(self) -> Path | None:
        record = self._active_pdf_record()
        if record is not None and record.has_valid_pdf:
            return record.last_successful_pdf
        self.statusBar().showMessage("还没有可用的 PDF，请先编译成功一次。", 5000)
        return None

    def _update_pdf_action_state(self) -> None:
        root = self._compile_root_for_tab(self.current_tab())
        record = self._active_pdf_record()
        preview = self._active_preview_record()
        export_ready = bool(
            (record is not None and record.has_valid_pdf)
            or (preview is not None and preview.has_valid_pdf)
        )
        canonical_ready = record is not None and record.export_allowed
        self.export_pdf_action.setEnabled(export_ready)
        self.pdf_panel.export_pdf_button.setEnabled(export_ready)
        self.reveal_pdf_action.setEnabled(canonical_ready)
        self.pdf_panel.reveal_pdf_button.setEnabled(canonical_ready)
        displayed = self.displayed_pdfs.get(root) if root is not None else None
        self.sync_pdf_action.setEnabled(
            displayed is not None
            and displayed.purpose is BuildPurpose.FINAL
            and record is not None
            and record.freshness is PdfFreshness.CURRENT
            and record.last_successful_revision == record.source_revision
        )

        if displayed is not None and displayed.purpose is BuildPurpose.PREVIEW and preview is not None:
            if preview.freshness is PreviewFreshness.CURRENT:
                fidelity = {
                    "proxy": "代理图",
                    "mixed": "部分代理图",
                    "original_fallback": "原图回退",
                    "original": "无需代理",
                }.get(preview.fidelity, "原图回退")
                self.pdf_panel.set_freshness(
                    f"快速预览已更新（{fidelity}）· 导出时使用原图",
                    "success",
                )
            else:
                self.pdf_panel.set_freshness(
                    PREVIEW_FRESHNESS_LABELS[preview.freshness],
                    PREVIEW_FRESHNESS_SEVERITY[preview.freshness],
                )
            return
        if displayed is not None and displayed.purpose is BuildPurpose.FINAL:
            freshness = record.freshness if record is not None else PdfFreshness.UNCOMPILED
            self.pdf_panel.set_freshness(FRESHNESS_LABELS[freshness], FRESHNESS_SEVERITY[freshness])
            return
        if preview is not None and preview.freshness in (
            PreviewFreshness.COMPILING,
            PreviewFreshness.FAILED_STALE,
            PreviewFreshness.FAILED_NO_PDF,
        ):
            self.pdf_panel.set_freshness(
                PREVIEW_FRESHNESS_LABELS[preview.freshness],
                PREVIEW_FRESHNESS_SEVERITY[preview.freshness],
            )
            return
        freshness = record.freshness if record is not None else PdfFreshness.UNCOMPILED
        self.pdf_panel.set_freshness(FRESHNESS_LABELS[freshness], FRESHNESS_SEVERITY[freshness])

    def export_pdf(self) -> bool:
        root = self._compile_root_for_tab(self.current_tab())
        record = self._active_pdf_record()
        preview = self._active_preview_record()
        if root is None or not (
            (record is not None and record.has_valid_pdf)
            or (preview is not None and preview.has_valid_pdf)
        ):
            self.statusBar().showMessage("还没有可用的 PDF，请先编译成功一次。", 5000)
            return False
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "导出正式 PDF（使用原图）",
            str(Path.home() / f"{root.stem}.pdf"),
            "PDF 文件 (*.pdf)",
        )
        if not file_name:
            return False
        target = Path(file_name).expanduser()
        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")
        return self.pdf_export.request_export(root, target)

    def notify_pdf_export_status(self, message: str, duration_ms: int) -> None:
        self.statusBar().showMessage(message, duration_ms)

    def notify_pdf_export_error(self, message: str) -> None:
        self.append_log(message)
        QMessageBox.warning(self, "导出失败", message)

    def reveal_pdf(self) -> None:
        pdf = self._compiled_pdf_path()
        if pdf is None:
            return
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(pdf)])
            elif sys.platform.startswith("win"):
                subprocess.Popen(["explorer", f"/select,{pdf}"])
            elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf.parent))):
                raise OSError("系统没有可用的文件管理器")
        except OSError as exc:
            self.append_log(f"无法打开文件管理器：{exc}")
            self.statusBar().showMessage(f"无法打开文件管理器：{exc}", 6000)

    def compile_current(
        self,
        *,
        immediate: bool = False,
        show_missing_warning: bool = False,
        purpose: BuildPurpose | None = None,
    ) -> None:
        self.compile.compile_current(
            immediate=immediate,
            show_missing_warning=show_missing_warning,
            purpose=purpose,
        )

    def stop_compile_current(self) -> None:
        self.compile.stop_current()

    def clean_build_cache(self) -> bool:
        return self.compile.clean_build_cache()

    def full_rebuild_current(self) -> None:
        self.compile.full_rebuild()

    def update_word_count(self) -> None:
        tab = self.current_tab()
        if not tab:
            self.word_count_view.reset("未选择文档")
            return
        root = self._compile_root_for_tab(tab)
        if tab.path is not None and root is not None:
            overrides: dict[Path, str] = {}
            for candidate in self.tabs.values():
                if candidate.path is None:
                    continue
                if self._compile_root_for_tab(candidate) == root:
                    overrides[normalize_path(candidate.path)] = candidate.editor.toPlainText()
            result = count_project(root, overrides, self.toolchain)
            document_name = root.name
        else:
            result = count_text(tab.editor.toPlainText(), tab.path, self.toolchain)
            document_name = "未保存文档"
        is_modified = tab.modified or tab.dirty or tab.path is None
        self.word_count_view.set_result(result, document_name, is_modified)

    def run_project_check(
        self,
        log_errors: list[LaTeXError] | None = None,
        *,
        switch_to_panel: bool = True,
    ) -> list[Diagnostic]:
        return self.project_panels.run_project_check(log_errors, switch_to_panel=switch_to_panel)

    def show_environment_doctor(self) -> None:
        report = build_environment_report(self.toolchain)
        dialog = EnvironmentDoctorDialog(report, self, feedback_context_provider=self._build_feedback_context)
        dialog.exec()

    def show_user_guide(self) -> None:
        UserGuideDialog(self).exec()

    def copy_feedback_bundle(self) -> None:
        report = build_environment_report(self.toolchain)
        # The one-click action is privacy-first: raw TeX logs can echo source
        # lines and local paths, so only the inspectable Environment Doctor
        # flow includes them.
        context = self._build_feedback_context(include_recent_log=False)
        bundle = build_feedback_bundle(
            report,
            recent_log=context.recent_log,
            diagnostics=context.diagnostics,
            project_file=context.project_file,
            metadata=context.metadata,
        )
        QApplication.clipboard().setText(bundle)
        self.statusBar().showMessage("反馈包已复制；不包含论文正文和原始编译日志。", 5000)

    def _build_feedback_context(self, *, include_recent_log: bool = True) -> FeedbackContext:
        tab = self.current_tab()
        project_file = tab.path if tab is not None else None
        recent_log = (
            self.log_view.toPlainText()
            if include_recent_log and hasattr(self, "log_view")
            else None
        )
        diagnostics = list(self.diagnostic_panel.diagnostics) if hasattr(self, "diagnostic_panel") else []
        root_info = resolve_root_tex(project_file) if project_file is not None else None
        metadata = FeedbackMetadata(
            selected_engine=self.current_engine.display_name,
            root_file=root_info.root if root_info is not None else None,
            root_source=root_info.source_label if root_info is not None else "unknown",
            latest_compile_seconds=self._latest_compile_seconds_for_feedback(),
            word_count_mode=getattr(self.word_count_view, "last_mode_label", None),
        )
        return FeedbackContext(
            recent_log=recent_log,
            diagnostics=diagnostics,
            project_file=project_file,
            metadata=metadata,
        )

    def _latest_compile_seconds_for_feedback(self) -> float | None:
        if not hasattr(self, "compile_time_label"):
            return None
        text = self.compile_time_label.text().strip()
        if not text.startswith("上次编译 ") or not text.endswith("s"):
            return None
        try:
            return float(text.removeprefix("上次编译 ").removesuffix("s"))
        except ValueError:
            return None

    def fix_diagnostic(self, index: int) -> None:
        self.project_panels.fix_diagnostic(index)

    def jump_to_diagnostic(self, index: int) -> None:
        self.project_panels.jump_to_diagnostic(index)

    def update_document_view_state(self) -> None:
        if not hasattr(self, "source_stack"):
            return
        has_documents = self.editor_tabs.count() > 0
        self.source_stack.setCurrentWidget(self.editor_tabs if has_documents else self.welcome_page)
        for action in (
            self.save_action,
            self.save_as_action,
            self.compile_action,
            self.clean_build_action,
            self.full_rebuild_action,
            self.health_check_action,
            self.word_count_action,
            self.find_action,
            self.replace_action,
        ):
            action.setEnabled(has_documents)
        self._update_pdf_action_state()
        if not has_documents:
            self.find_replace_bar.close_bar()
            self.update_welcome_page()

    def update_welcome_page(self) -> None:
        self.preferences_controller.update_welcome_page()

    def show_find_bar(self) -> None:
        tab = self.current_tab()
        self.find_replace_bar.set_editor(tab.editor if tab else None)
        self.find_replace_bar.show_find()

    def show_replace_bar(self) -> None:
        tab = self.current_tab()
        self.find_replace_bar.set_editor(tab.editor if tab else None)
        self.find_replace_bar.show_replace()

    def show_settings_dialog(self) -> None:
        self.preferences_controller.show_settings_dialog()

    def apply_preferences(self, preferences: AppPreferences, *, save: bool = False) -> None:
        self.preferences_controller.apply_preferences(preferences, save=save)

    def _preferences_from_ui(self) -> AppPreferences:
        return self.preferences_controller.preferences_from_ui()

    def _persist_preferences_from_ui(self, *_args: object) -> None:
        self.preferences_controller.persist_preferences_from_ui()

    def update_recent_menu(self) -> None:
        self.preferences_controller.update_recent_menu()

    def open_recent_file(self, path: Path) -> None:
        self.preferences_controller.open_recent_file(path)

    def open_recent_project(self, path: Path) -> None:
        self.preferences_controller.open_recent_project(path)

    def _remember_recent_file(self, path: Path) -> None:
        self.preferences_controller.remember_recent_file(path)

    def _remember_recent_project(self, path: Path) -> None:
        self.preferences_controller.remember_recent_project(path)

    def on_current_tab_changed(self, _index: int) -> None:
        tab = self.current_tab()
        self.find_replace_bar.set_editor(tab.editor if tab else None)
        self._sync_pdf_panel_to_active_root()
        self._sync_compile_indicators_to_active_root()
        self.update_word_count()
        self.refresh_project_panels()

    def _sync_compile_indicators_to_active_root(self) -> None:
        """Progress bar, timer, and stop button reflect only the active root."""
        root = self._compile_root_for_tab(self.current_tab())
        started_at = self.compile_start_times.get(root) if root is not None else None
        if started_at is not None:
            self.compile_started_at = started_at
            self.compile_progress.show()
            self.stop_compile_action.setEnabled(True)
            if not self.compile_timer.isActive():
                self.compile_timer.start()
            set_dynamic_property(self.compile_time_label, "state", "active")
            self.compile.update_timer()
            return
        self.compile_started_at = None
        self.compile_timer.stop()
        self.compile_progress.hide()
        self.stop_compile_action.setEnabled(False)
        displayed = self.displayed_pdfs.get(root) if root is not None else None
        record = self.pdf_state.record_for(root) if root is not None else None
        preview = self.preview_state.record_for(root) if root is not None else None
        if (
            displayed is not None
            and displayed.purpose is BuildPurpose.PREVIEW
            and preview is not None
            and preview.last_duration_seconds is not None
        ):
            self.compile_time_label.setText(f"上次预览 {preview.last_duration_seconds:.2f}s")
            ok = preview.freshness is PreviewFreshness.CURRENT
            set_dynamic_property(self.compile_time_label, "state", "success" if ok else "error")
        elif record is not None and record.last_duration_seconds is not None:
            self.compile_time_label.setText(f"上次编译 {record.last_duration_seconds:.2f}s")
            ok = record.last_outcome is CompileOutcome.SUCCESS
            set_dynamic_property(self.compile_time_label, "state", "success" if ok else "error")
        else:
            self.compile_time_label.setText("空闲")
            set_dynamic_property(self.compile_time_label, "state", "")

    def refresh_project_panels(self) -> None:
        self.project_panels.refresh()

    def sync_current_source_to_pdf(self) -> None:
        tab = self.current_tab()
        if not tab or not tab.path or not tab.manager:
            return
        root = self._compile_root_for_tab(tab)
        displayed = self.displayed_pdfs.get(root) if root is not None else None
        record = self._active_pdf_record()
        if (
            displayed is None
            or displayed.purpose is not BuildPurpose.FINAL
            or record is None
            or record.freshness is not PdfFreshness.CURRENT
            or record.last_successful_revision != record.source_revision
        ):
            self.statusBar().showMessage("SyncTeX 需要当前版本的正式 PDF；请先执行正式编译。", 5000)
            return
        if not self.toolchain.synctex:
            QMessageBox.warning(self, "SyncTeX 不可用", "未找到 synctex。请安装完整 LaTeX 发行版后重启 ICSTeX。")
            return
        cursor = tab.editor.textCursor()
        line = cursor.blockNumber() + 1
        position = source_to_pdf(tab.path, line, displayed.path, self.toolchain)
        if position and position.page:
            if position.x is not None and position.y is not None:
                self.pdf_panel.jump_to_pdf_position(position.page, position.x, position.y)
            self.statusBar().showMessage(f"已同步源码第 {line} 行到 PDF 第 {position.page} 页。", 4000)
        else:
            self.statusBar().showMessage("暂时没有可用的 SyncTeX 源码到 PDF 数据。", 5000)

    def sync_pdf_to_source(self, page: int, x: float, y: float) -> None:
        # Only the active root's own PDF may drive SyncTeX; never fall back to
        # a viewer path left behind by another tab.
        root = self._compile_root_for_tab(self.current_tab())
        displayed = self.displayed_pdfs.get(root) if root is not None else None
        record = self._active_pdf_record()
        if (
            displayed is None
            or displayed.purpose is not BuildPurpose.FINAL
            or record is None
            or record.freshness is not PdfFreshness.CURRENT
            or record.last_successful_revision != record.source_revision
        ):
            self.statusBar().showMessage("SyncTeX 需要当前版本的正式 PDF；请先执行正式编译。", 5000)
            return
        pdf_file = (
            record.last_successful_pdf if record is not None and record.has_valid_pdf else None
        )
        if pdf_file is None:
            self.statusBar().showMessage("当前文档还没有可用的 PDF，无法定位源码。", 5000)
            return
        if not self.toolchain.synctex:
            self.statusBar().showMessage("未找到 synctex，暂时无法进行 PDF 到源码同步。", 5000)
            return
        position = pdf_to_source(pdf_file, page, x, y, self.toolchain)
        if position:
            self.open_file(position.file, position.line)
        else:
            self.statusBar().showMessage("该位置没有可用的 SyncTeX PDF 到源码数据。", 5000)

    def jump_to_error(self, row: int, _column: int) -> None:
        self.project_panels.jump_to_error(row)

    def reload_external_change(self, file_name: str) -> None:
        self.documents.reload_external_change(file_name)

    def spawn_window(self) -> None:
        window = MainWindow(settings_store=self.app_settings)
        window.show()
        QApplication.instance()._icstex_windows.append(window)  # type: ignore[attr-defined]

    def on_compile_started(self, root_file: str, build_id: int) -> None:
        self.compile.on_started(root_file, build_id)

    def on_compile_finished(self, result: CompileResult) -> None:
        self.compile.on_finished(result)

    def append_log(self, message: str) -> None:
        self.log_view.append(message)

    def _install_log_bridge(self) -> None:
        bridge = QtLogBridge(self)
        for module in ("app.core.compiler", "app.core.synctex", "app.core.file_watcher"):
            bridge.install_on(module)
        bridge.messageEmitted.connect(self._on_bridged_log)
        self._log_bridge = bridge

    def _on_bridged_log(self, _name: str, levelno: int, message: str) -> None:
        if levelno >= 30:
            self.log_view.append(f"[!] {message}")
        else:
            self.log_view.append(message)

    def update_compile_timer(self) -> None:
        self.compile.update_timer()

    def close_tab(self, index: int) -> None:
        self.tab_manager.close_at(index)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.tab_manager.handle_close_event(event)
        self.app_settings.settings.setValue("window/block_console_state", self.saveState())

    def current_tab(self) -> EditorTab | None:
        return self.tab_manager.current()

    def _ensure_editable_tab(self) -> EditorTab | None:
        return self.tab_manager.ensure_editable()

    def _require_saved_tab_for_assets(self) -> EditorTab | None:
        return self.tab_manager.require_saved_for_assets()

    def _bib_file_for_tab(self, tab: EditorTab, *, create: bool = False) -> Path | None:
        return bib_helpers.bib_file_for_tab(tab, create=create)

    def _bib_text_for_tab(self, tab: EditorTab) -> str:
        return bib_helpers.bib_text_for_tab(tab)

    def _ensure_bibliography_block(self, tab: EditorTab) -> None:
        bib_helpers.ensure_bibliography_block(tab)

    def _make_editor(self, text: str) -> LaTeXEditor:
        return self.documents.make_editor(text)

    def _apply_editor_font(self, editor: LaTeXEditor) -> None:
        self.documents.apply_editor_font(editor)

    def _insert_generated_snippet(
        self,
        tab: EditorTab,
        snippet: str,
        packages: tuple[str, ...],
        message: str,
        *,
        cursor_offset: int | None = None,
        block: bool = True,
    ) -> None:
        self.insertions.insert_snippet(
            tab, snippet, packages, message, cursor_offset=cursor_offset, block=block
        )

    def _add_tab(self, tab: EditorTab, title: str) -> None:
        self.tab_manager.add(tab, title)

    def _save_tab(self, tab: EditorTab, path: Path) -> bool:
        return self.documents.save_tab(tab, path)

    def _create_history_snapshot(self, path: Path, text: str, label: str) -> None:
        self.documents.create_history_snapshot(path, text, label)

    def _on_editor_changed(self) -> None:
        sender = self.sender()
        tab = self.tabs.get(id(sender)) if sender is not None else None
        if tab is None:
            tab = self.current_tab()
        if not tab:
            return
        tab.modified = True
        tab.dirty = True
        self._mark_source_edited(tab)
        if tab is self.current_tab():
            self._update_pdf_action_state()
        self._set_tab_title(tab)
        if tab.path:
            self.schedule_save(tab, compile_after_save=self.auto_compile_action.isChecked())
        else:
            self.statusBar().showMessage("未保存文档有待保存修改。", 2000)
        if self.sidebar_tabs.currentIndex() in (1, 3, 4, 7, 8):
            self.refresh_project_panels()

    def schedule_save(self, tab: EditorTab, *, compile_after_save: bool = False) -> None:
        self.documents.schedule_save(tab, compile_after_save=compile_after_save)

    def flush_pending_save(self, tab: EditorTab, *, compile_after_save: bool | None = None) -> bool:
        return self.documents.flush_pending_save(tab, compile_after_save=compile_after_save)

    def _compile_after_idle_save(self, tab: EditorTab) -> None:
        self.documents.compile_after_idle(tab)

    def _cancel_save_timer(self, tab: EditorTab) -> None:
        self.documents.cancel_save_timer(tab)

    def _set_tab_title(self, tab: EditorTab) -> None:
        self.tab_manager.set_title(tab)

    def _show_errors(self, result: CompileResult) -> None:
        self.compile.show_errors(result)

    def _show_toolchain_status(self) -> None:
        self.compile.show_toolchain_status()

    def _watch_file(self, path: Path) -> None:
        self.tab_manager.watch_path(path)

    def _tab_for_path(self, path: Path) -> EditorTab | None:
        return self.tab_manager.for_path(path)

    def _index_for_tab_id(self, tab_id: int) -> int:
        return self.tab_manager.index_for_tab_id(tab_id)

    def _jump_to_line(self, editor: LaTeXEditor, line: int) -> None:
        view_state.jump_to_line(editor, line)

    def _jump_to_position(self, editor: LaTeXEditor, line: int, column: int) -> None:
        view_state.jump_to_position(editor, line, column)

    def _capture_editor_view_state(self, editor: LaTeXEditor) -> EditorViewState:
        return view_state.capture(editor)

    def _restore_editor_view_state(self, editor: LaTeXEditor, state: EditorViewState) -> None:
        view_state.restore(editor, state)

    def apply_editor_options(self, editor: LaTeXEditor) -> None:
        self.preferences_controller.apply_editor_options(editor)

    def apply_editor_options_to_all(self, *_args: object) -> None:
        self.preferences_controller.apply_editor_options_to_all()

    def on_engine_selector_changed(self, index: int) -> None:
        self.compile.on_engine_selector_changed(index)

    def set_engine(self, engine: LaTeXEngine, *, from_selector: bool = False) -> None:
        self.compile.set_engine(engine, from_selector=from_selector)

    def rebuild_compile_managers(self) -> None:
        self.compile.rebuild_managers()

    def create_compile_manager(self, path: Path) -> CompileManager:
        return self.compile.create_manager(path)


def run(argv: list[str] | None = None) -> int:
    configure_logging()
    QApplication.setDesktopSettingsAware(False)
    app = QApplication(argv or sys.argv)
    app.setApplicationName(__app_name__)
    cover_path = app_cover_path()
    if cover_path.exists():
        app.setWindowIcon(QIcon(str(cover_path)))
    apply_theme(app)
    app._icstex_windows = []  # type: ignore[attr-defined]
    window = MainWindow()
    window.show()
    app._icstex_windows.append(window)  # type: ignore[attr-defined]
    return app.exec()
