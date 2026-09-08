"""Compile lifecycle, engine selection, toolchain status, and error-table updates.

Controller holds a back-reference to ``MainWindow``. The ``CompileSignals`` Qt
object still lives on the window so existing ``signals.started.connect(...)``
wiring keeps working unchanged.
"""
from __future__ import annotations

from dataclasses import replace
import logging
from pathlib import Path
import shutil
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem

from app.core.compile_feedback import headline_for, presentation_for
from app.core.compiler import (
    BuildPurpose,
    CompileJobKey,
    CompileManager,
    CompileOutcome,
    CompileResult,
    PreviewPreparation,
)
from app.core.diagnostics import explain_latex_error
from app.core.latex_tools import LaTeXEngine
from app.core.magic_comments import magic_engine_for
from app.core.project_dependencies import safe_project_input
from app.core.paths import (
    build_dir_for,
    normalize_path,
    preview_assets_dir_for,
    preview_root_dir_for,
    resolve_root_tex,
)
from app.core.import_metrics import import_metrics
from app.gui.image_proxy_cache import ImageProxyCache
from app.gui.main_window_support import set_dynamic_property

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.gui.main_window import MainWindow


logger = logging.getLogger(__name__)


class CompileController:
    def __init__(self, window: "MainWindow") -> None:
        self.window = window
        self.image_proxy_cache = ImageProxyCache()
        self._job_keys: dict[tuple[Path, int], CompileJobKey] = {}

    # --- main entry points --------------------------------------------------

    def compile_current(
        self,
        *,
        immediate: bool = False,
        show_missing_warning: bool = False,
        purpose: BuildPurpose | None = None,
        user_initiated: bool = True,
    ) -> None:
        window = self.window
        # Calling this entry point is a deliberate/manual compile unless an
        # auto-save caller explicitly requests PREVIEW.
        selected_purpose = purpose or BuildPurpose.FINAL
        tab = window.current_tab()
        if not tab:
            return
        if not user_initiated and not window.auto_compile_action.isChecked():
            return
        root = window._compile_root_for_tab(tab)
        if root is not None:
            root = normalize_path(root)
            if user_initiated:
                window.compile_authorized_roots.add(root)
            elif root not in window.compile_authorized_roots:
                window.statusBar().showMessage("首次编译需由你显式触发；当前仅保存修改。", 4000)
                return
        if not window.toolchain.is_compile_ready:
            if root is not None:
                if selected_purpose is BuildPurpose.PREVIEW:
                    window.preview_state.record_failed_attempt(root)
                else:
                    window.pdf_state.record_failed_attempt(root, CompileOutcome.TOOLCHAIN_MISSING)
                window._update_pdf_action_state()
            presentation = presentation_for(CompileOutcome.TOOLCHAIN_MISSING)
            window.statusBar().showMessage(f"{presentation.title}：{presentation.next_action}", 6000)
            if show_missing_warning:
                window.append_log(window.toolchain.missing_compile_message)
                QMessageBox.warning(window, "未找到 LaTeX 编译器", window.toolchain.missing_compile_message)
            return
        if tab.path is None:
            if not window.save_current_as():
                return
        elif tab.dirty or tab.modified or (tab.save_timer is not None and tab.save_timer.isActive()):
            if not window.flush_pending_save(tab, compile_after_save=False):
                return
        if tab.path is None:
            return
        root = window._compile_root_for_tab(tab)
        if root is not None and not window.documents.flush_root_documents(root):
            return
        if tab.manager is None:
            tab.manager = self.create_manager(tab.path)
        else:
            # Re-read magic comments on every compile so editing
            # "% !TEX program=" in an already-open AUTO-mode document takes
            # effect immediately, instead of only on the next file open.
            tab.manager.engine = self._effective_engine_for(tab.path, tab.manager.root_file)
        self.sync_input_revision(tab.manager.root_file)
        if immediate:
            tab.manager.cancel_pending()
            tab.manager.compile_async(selected_purpose)
        else:
            tab.manager.schedule_compile("手动触发/编辑器修改", selected_purpose)

    def stop_current(self) -> None:
        window = self.window
        tab = window.current_tab()
        if not tab or not tab.manager:
            window.statusBar().showMessage("当前没有正在运行的编译。", 3000)
            return
        was_busy = tab.manager.is_busy
        if tab.manager.stop_current():
            window.append_log("已请求停止当前编译。")
            window.statusBar().showMessage("当前编译已停止。", 3000)
        elif was_busy:
            window.statusBar().showMessage("已请求停止；编译准备阶段尚未退出。", 5000)
        else:
            window.statusBar().showMessage("当前没有正在运行的编译。", 3000)

    def clean_build_cache(self) -> bool:
        window = self.window
        tab = window.current_tab()
        if not tab or not tab.path:
            window.statusBar().showMessage("请先打开或保存一个 .tex 文件。", 4000)
            return False

        if tab.manager is not None:
            tab.manager.cancel_pending()
            if tab.manager.is_busy and not tab.manager.stop_current():
                QMessageBox.warning(
                    window,
                    "无法清理",
                    "编译准备阶段尚未停止；为避免缓存被并发重建，本次未删除任何文件。",
                )
                return False
            if not tab.manager.wait_until_idle(0):
                QMessageBox.warning(
                    window,
                    "无法清理",
                    "编译 worker 仍在运行；本次未删除任何文件。",
                )
                return False
            self.invalidate_manager_builds(tab.manager, transition_state=False)

        output_dir = tab.manager.output_dir if tab.manager else build_dir_for(tab.path)
        root = window._compile_root_for_tab(tab)
        preview_dir = preview_root_dir_for(root) if root is not None else None
        selected_scope = window.selected_project_scope
        if selected_scope is not None:
            selected_scope = selected_scope.resolve()
        if root is not None and selected_scope is not None and not root.is_relative_to(selected_scope):
            QMessageBox.warning(window, "拒绝清理", f"编译根目录超出当前项目范围：{root}")
            return False
        project_dir = (
            selected_scope
            if selected_scope is not None
            else (root.parent.resolve() if root is not None else tab.path.parent.resolve())
        )
        if output_dir.name != ".latex_build" or not output_dir.resolve().is_relative_to(project_dir):
            QMessageBox.warning(window, "拒绝清理", f"构建目录看起来不安全：{output_dir}")
            return False
        if preview_dir is not None and (
            preview_dir.parent.name != "preview" or preview_dir.parent.parent.name != ".icstex"
            or not preview_dir.resolve().is_relative_to(project_dir)
        ):
            QMessageBox.warning(window, "拒绝清理", f"预览目录看起来不安全：{preview_dir}")
            return False
        try:
            if output_dir.exists():
                shutil.rmtree(output_dir)
                window.append_log(f"已清理缓存：{output_dir}")
            else:
                window.append_log(f"缓存目录不存在，无需清理：{output_dir}")
            if preview_dir is not None and preview_dir.exists():
                shutil.rmtree(preview_dir)
                window.append_log(f"已清理快速预览缓存：{preview_dir}")
        except OSError as exc:
            QMessageBox.warning(window, "清理缓存失败", str(exc))
            return False
        if root is not None:
            window.pdf_state.clear_build_output(root)
            window.preview_state.clear_build_output(root)
            window.displayed_pdfs.pop(root, None)
            if hasattr(window, "pdf_export"):
                window.pdf_export.cancel_root(root)
        window._sync_pdf_panel_to_active_root()
        window.statusBar().showMessage("已清理编译缓存。", 4000)
        return True

    def full_rebuild(self) -> None:
        if self.clean_build_cache():
            self.compile_current(
                immediate=True,
                show_missing_warning=True,
                purpose=BuildPurpose.FINAL,
            )

    # --- compile signal slots ----------------------------------------------

    def _is_active_root(self, root_file: Path | str) -> bool:
        active = self.window._compile_root_for_tab(self.window.current_tab())
        return active is not None and active == normalize_path(root_file)

    def on_started(self, root_file: str, build_id: int) -> None:
        window = self.window
        root = normalize_path(root_file)
        key = (root, build_id)
        manager = window.compile_build_owners.get(key)
        if manager is None or not self._manager_owns_root(manager):
            window.compile_build_owners.pop(key, None)
            window.compile_purposes.pop(key, None)
            self._job_keys.pop(key, None)
            return
        purpose = window.compile_purposes.get(key, BuildPurpose.FINAL)
        job_key = self._job_keys.get(key)
        revision = job_key.source_revision if job_key is not None else None
        window.compile_active_builds[root] = (manager, build_id, purpose)
        window.compile_start_purposes[root] = purpose
        if purpose is BuildPurpose.PREVIEW:
            window.preview_state.begin_build(root, build_id, source_revision=revision)
        else:
            window.pdf_state.begin_build(root, build_id, source_revision=revision)
        if hasattr(window, "pdf_export"):
            window.pdf_export.handle_compile_started(root, build_id, purpose)
        window.compile_start_times[root] = time.perf_counter()
        # Background builds must not touch the active tab's status widgets.
        if self._is_active_root(root):
            window.compile_started_at = window.compile_start_times[root]
            window.compile_progress.show()
            window.stop_compile_action.setEnabled(True)
            window.compile_timer.start()
            self.update_timer()
            tab = self._tab_for_compile_root(root)
            engine = job_key.engine if job_key else (tab.manager.engine if tab and tab.manager else window.current_engine)
            window.status_engine_label.setText(engine.display_name)
            set_dynamic_property(window.compile_time_label, "state", "active")
            source_hint = ""
            current = window.current_tab()
            if current and current.path and normalize_path(current.path) != root:
                source_hint = f"（由 {current.path.name} 指向）"
            operation = "更新快速预览" if purpose is BuildPurpose.PREVIEW else "正式编译"
            window.statusBar().showMessage(
                f"正在使用 {engine.display_name}{operation} {root.name}{source_hint}..."
            )
        window._update_pdf_action_state()

    def on_finished(self, result: CompileResult) -> None:
        window = self.window
        root = normalize_path(result.root_file)
        key = (root, result.build_id)
        manager = window.compile_build_owners.get(key)
        active = window.compile_active_builds.get(root)
        if (
            manager is None
            or not self._manager_owns_root(manager)
            or active is None
            or active[0] is not manager
            or active[1] != result.build_id
        ):
            if window.compile_build_owners.get(key) is manager:
                window.compile_build_owners.pop(key, None)
            window.compile_purposes.pop(key, None)
            self._job_keys.pop(key, None)
            logger.info("已忽略不再归当前 manager 所有的编译结果：%s", result.root_file)
            return
        window.compile_build_owners.pop(key, None)
        window.compile_active_builds.pop(root, None)
        window.compile_start_times.pop(root, None)
        window.compile_start_purposes.pop(root, None)
        window.compile_purposes.pop(key, None)
        job_key = self._job_keys.pop(key, None)
        is_current = self._is_active_root(root)
        if is_current:
            window.compile_timer.stop()
            window.compile_progress.hide()
            window.stop_compile_action.setEnabled(False)
            window.compile_started_at = None
            label = "上次预览" if result.purpose is BuildPurpose.PREVIEW else "上次编译"
            window.compile_time_label.setText(f"{label} {result.duration_seconds:.2f}s")
            set_dynamic_property(window.compile_time_label, "state", "success" if result.ok else "error")
        compiled_tab = self._tab_for_compile_root(result.root_file)
        engine = job_key.engine if job_key else (
            compiled_tab.manager.engine if compiled_tab and compiled_tab.manager else window.current_engine
        )
        if result.purpose is BuildPurpose.PREVIEW:
            if result.preview_manifest_digest is not None:
                self.register_preview_assets(root, result.preview_asset_paths)
            record = window.preview_state.finish_build(
                result.root_file,
                result.build_id,
                success=result.ok,
                pdf_file=result.pdf_file if result.ok else None,
                duration_seconds=result.duration_seconds,
                engine=engine.display_name,
                fidelity=result.preview_fidelity,
                manifest_digest=result.preview_manifest_digest,
            )
        else:
            self.register_preview_assets(root, self.image_proxy_cache.referenced_paths(root))
            record = window.pdf_state.finish_build(
                result.root_file,
                result.build_id,
                result.outcome,
                pdf_file=result.pdf_file if result.ok else None,
                duration_seconds=result.duration_seconds,
                engine=engine.display_name,
            )
        if record is None:
            window.append_log(f"已忽略过期的编译结果：{result.root_file.name}")
            window._update_pdf_action_state()
            return
        window.dependencies.accept_build(result)
        headline = headline_for(result, engine_name=engine.display_name)
        if result.purpose is BuildPurpose.PREVIEW:
            headline = f"快速预览：{headline}"
        window.append_log(headline)
        if result.ok:
            window.append_log(f"PDF 输出：{result.pdf_file}")
            if is_current:
                window._sync_pdf_panel_to_active_root()
            if result.purpose is BuildPurpose.FINAL:
                tab = window._tab_for_path(result.root_file)
                if tab is not None:
                    window._create_history_snapshot(result.root_file, tab.editor.toPlainText(), "编译成功")
        else:
            window.append_log(f"编译进程退出码 {result.returncode}。")
            presentation = presentation_for(result.outcome)
            window.append_log(f"建议：{presentation.next_action}")
            if result.errors:
                window.append_log("解析到的 LaTeX 错误：")
                for error in result.errors[:8]:
                    window.append_log(f"  - {error.display()}")
                if len(result.errors) > 8:
                    window.append_log(f"  ... 还有 {len(result.errors) - 8} 个错误")
            if result.stderr:
                window.append_log(result.stderr.strip())
        if is_current:
            window.statusBar().showMessage(headline, 4000 if result.ok else 6000)
            self.show_errors(result)
            window.run_project_check(result.errors if not result.ok else [], switch_to_panel=not result.ok)
            window.update_word_count()
        if result.purpose is BuildPurpose.FINAL and hasattr(window, "pdf_export"):
            window.pdf_export.handle_compile_result(result, record)
        window._update_pdf_action_state()

    def update_timer(self) -> None:
        window = self.window
        if window.compile_started_at is None:
            return
        elapsed = time.perf_counter() - window.compile_started_at
        root = window._compile_root_for_tab(window.current_tab())
        purpose = window.compile_start_purposes.get(root, BuildPurpose.FINAL)
        label = "预览中" if purpose is BuildPurpose.PREVIEW else "编译中"
        window.compile_time_label.setText(f"{label} {elapsed:.1f}s")

    # --- presentation -------------------------------------------------------

    def show_errors(self, result: CompileResult) -> None:
        window = self.window
        window.error_table.setRowCount(0)
        for error in result.errors:
            diagnostic = explain_latex_error(error, root_file=result.root_file)
            row = window.error_table.rowCount()
            window.error_table.insertRow(row)
            file_item = QTableWidgetItem(error.file.name if error.file else result.root_file.name)
            file_item.setData(Qt.ItemDataRole.UserRole, str(error.file or result.root_file))
            file_item.setToolTip(str(error.file or result.root_file))
            line_item = QTableWidgetItem(str(error.line or ""))
            line_item.setToolTip(str(error.line or ""))
            message_item = QTableWidgetItem(f"{diagnostic.title}：{diagnostic.message}")
            message_item.setToolTip(error.message)
            window.error_table.setItem(row, 0, file_item)
            window.error_table.setItem(row, 1, line_item)
            window.error_table.setItem(row, 2, message_item)
        error_count = window.error_table.rowCount()
        index = window.bottom_tabs.indexOf(window.error_table)
        if index >= 0:
            window.bottom_tabs.setTabText(index, f"错误 {error_count}" if error_count else "错误")

    def show_toolchain_status(self) -> None:
        window = self.window
        window.update_welcome_page()
        if window.toolchain.is_compile_ready:
            window.statusBar().showMessage(
                f"就绪 | 编译器：{window.toolchain.compiler_name} | 引擎：{window.current_engine.display_name}",
                5000,
            )
        else:
            window.statusBar().showMessage("LaTeX 环境未就绪：请先安装 LaTeX 发行版。", 8000)

    # --- compile manager factory -------------------------------------------

    def create_manager(self, path: Path) -> CompileManager:
        # One shared CompileManager per normalized root: root and child tabs
        # serialize builds instead of racing over the same .latex_build.
        window = self.window
        root_info = resolve_root_tex(path, selected_scope=window.selected_project_scope)
        root_file = normalize_path(root_info.root or path)
        engine = self._effective_engine_for(path, root_file)
        manager = window.compile_managers.get(root_file)
        if manager is not None:
            manager.engine = engine
            self.sync_input_revision(root_file)
            return manager
        manager = CompileManager(
            root_file,
            toolchain=window.toolchain,
            engine=engine,
            debounce_ms=window.compile_debounce_ms,
            preview_preparer=self._prepare_preview,
            metrics_hook=import_metrics.record_compile_event,
            project_scope=window.selected_project_scope or root_file.parent,
        )
        manager.on_started = lambda root, build_id: self._emit_started(manager, root, build_id)
        manager.on_finished = lambda result: self._emit_finished(manager, result)
        window.compile_managers[root_file] = manager
        self.sync_input_revision(root_file)
        window.dependencies.refresh_memberships()
        return manager

    def sync_input_revision(self, root: Path) -> None:
        window = self.window
        manager = window.compile_managers.get(root)
        if manager is not None:
            manager.set_input_revision(
                window.pdf_state.record_for(root).source_revision,
                window.dependencies.generation_for(root),
            )

    def _emit_started(self, manager: CompileManager, root: Path, build_id: int) -> None:
        normalized = normalize_path(root)
        if not self._manager_owns_root(manager):
            return
        key = (normalized, build_id)
        self.window.compile_build_owners[key] = manager
        self.window.compile_purposes[key] = manager.active_purpose
        job_key = manager.active_job_key
        if job_key is not None:
            self._job_keys[key] = job_key
        self.window.signals.started.emit(str(normalized), build_id)

    def _emit_finished(self, manager: CompileManager, result: CompileResult) -> None:
        root = normalize_path(result.root_file)
        key = (root, result.build_id)
        if (
            not self._manager_owns_root(manager)
            or self.window.compile_build_owners.get(key) is not manager
        ):
            self.window.compile_build_owners.pop(key, None)
            self.window.compile_purposes.pop(key, None)
            self._job_keys.pop(key, None)
            return
        self.window.signals.finished.emit(result)

    def _manager_owns_root(self, manager: CompileManager) -> bool:
        return (
            not manager.is_retired
            and self.window.compile_managers.get(manager.root_file) is manager
        )

    def invalidate_manager_builds(
        self,
        manager: CompileManager,
        *,
        transition_state: bool = True,
    ) -> None:
        """Invalidate queued/active callbacks belonging to one manager instance."""
        window = self.window
        owned_keys = [
            key for key, owner in window.compile_build_owners.items() if owner is manager
        ]
        invalidated_active_root = False
        for key in owned_keys:
            root, build_id = key
            active = window.compile_active_builds.get(root)
            purpose = window.compile_purposes.get(key, BuildPurpose.FINAL)
            if active is not None and active[0] is manager and active[1] == build_id:
                if transition_state:
                    if purpose is BuildPurpose.PREVIEW:
                        window.preview_state.finish_build(root, build_id, success=False)
                    else:
                        window.pdf_state.finish_build(root, build_id, CompileOutcome.STOPPED)
                window.compile_active_builds.pop(root, None)
                window.compile_start_times.pop(root, None)
                window.compile_start_purposes.pop(root, None)
                invalidated_active_root = invalidated_active_root or self._is_active_root(root)
            window.compile_build_owners.pop(key, None)
            window.compile_purposes.pop(key, None)
            self._job_keys.pop(key, None)
        if invalidated_active_root:
            window._sync_compile_indicators_to_active_root()
            window._update_pdf_action_state()

    def retire_manager(self, manager: CompileManager, *, timeout: float = 1.5) -> bool:
        """Revoke GUI ownership before waiting for a manager to stop."""
        window = self.window
        if window.compile_managers.get(manager.root_file) is manager:
            window.compile_managers.pop(manager.root_file, None)
        self.invalidate_manager_builds(manager)
        stopped = manager.retire(timeout)
        if not stopped:
            logger.warning("旧编译 manager 未在 %.1fs 内退出：%s", timeout, manager.root_file)
        return stopped

    def _prepare_preview(self, root_file: Path, _output_dir: Path) -> PreviewPreparation:
        result = self.image_proxy_cache.prepare(root_file, preview_assets_dir_for(root_file))
        overlay = result.overlay_dir if result.proxy_count > 0 else None
        if result.proxy_count:
            message = (
                f"快速预览图片：{result.proxy_count} 个代理图，"
                f"{result.fallback_count} 个原图回退。"
            )
        elif result.fallback_count:
            message = f"快速预览图片：{result.fallback_count} 个引用使用原图回退。"
        else:
            message = "快速预览：当前文档没有可代理的 PNG/JPEG 图片。"
        return PreviewPreparation(
            overlay_dir=overlay,
            fidelity=result.fidelity,
            manifest_digest=result.manifest_digest,
            asset_paths=result.referenced_paths,
            message=message,
        )

    def register_preview_assets(self, root: Path, paths: tuple[Path, ...]) -> None:
        window = self.window
        normalized_root = normalize_path(root)
        previous = window.preview_root_assets.get(normalized_root, set())
        scope = window.selected_project_scope or normalized_root.parent
        current = {
            safe for path in paths
            if (safe := safe_project_input(scope, path)) is not None
        }
        # Keep watching a referenced path after deletion so an atomic save or
        # later recreation is observed. Existing paths disappear from this set
        # when the TeX reference itself is removed; missing paths are released
        # when the root closes.
        current.update(path for path in previous if not path.exists())
        for path in previous - current:
            roots = window.preview_asset_roots.get(path)
            if roots is None:
                continue
            roots.discard(normalized_root)
            if not roots:
                window.preview_asset_roots.pop(path, None)
        for path in current - previous:
            window.preview_asset_roots.setdefault(path, set()).add(normalized_root)
        window.preview_root_assets[normalized_root] = current
        window.dependencies.register_extra(normalized_root, tuple(current))

    def release_preview_assets(self, root: Path) -> None:
        normalized_root = normalize_path(root)
        paths = self.window.preview_root_assets.pop(normalized_root, set())
        for path in paths:
            roots = self.window.preview_asset_roots.get(path)
            if roots is None:
                continue
            roots.discard(normalized_root)
            if not roots:
                self.window.preview_asset_roots.pop(path, None)
        self.window.dependencies.register_extra(normalized_root, ())

    def handle_external_asset_change(self, path: Path) -> bool:
        return self.window.dependencies.handle_external_change(path)

    def rebuild_managers(self) -> None:
        window = self.window
        for manager in tuple(window.compile_managers.values()):
            self.retire_manager(manager)
        for tab in window.tabs.values():
            if tab.path:
                tab.manager = self.create_manager(tab.path)

    # --- engine selection ---------------------------------------------------

    def on_engine_selector_changed(self, index: int) -> None:
        engine_value = self.window.engine_selector.itemData(index)
        if engine_value:
            self.set_engine(LaTeXEngine(engine_value), from_selector=True)

    def set_engine(self, engine: LaTeXEngine, *, from_selector: bool = False) -> None:
        window = self.window
        if window.current_engine == engine:
            return
        window.current_engine = engine
        window.status_engine_label.setText(engine.display_name)
        window.preferences = replace(window.preferences, default_engine=engine)
        window.app_settings.save_preferences(window.preferences)
        if not from_selector:
            index = window.engine_selector.findData(engine.value)
            if index >= 0:
                window.engine_selector.blockSignals(True)
                window.engine_selector.setCurrentIndex(index)
                window.engine_selector.blockSignals(False)
        for menu_engine, action in window.engine_actions.items():
            action.blockSignals(True)
            action.setChecked(menu_engine == engine)
            action.blockSignals(False)
        self.rebuild_managers()
        window.update_welcome_page()
        window.statusBar().showMessage(f"编译引擎已切换为 {engine.display_name}。", 4000)
        current = window.current_tab()
        if current and current.path:
            self.compile_current(immediate=True)

    # --- magic comments ----------------------------------------------------

    def _effective_engine_for(self, source_file: Path, root_file: Path) -> LaTeXEngine:
        window = self.window
        if window.current_engine != LaTeXEngine.AUTO:
            return window.current_engine
        return magic_engine_for(source_file) or magic_engine_for(root_file) or LaTeXEngine.AUTO

    def _tab_for_compile_root(self, root_file: Path):
        root = root_file.resolve()
        for tab in self.window.tabs.values():
            if tab.manager and tab.manager.root_file == root:
                return tab
        return None
