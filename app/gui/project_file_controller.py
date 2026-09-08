"""Project file-tree navigation and guarded filesystem mutations."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from PySide6.QtCore import QEvent, QModelIndex, QObject, QPoint, QTimer
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMenu, QMessageBox

from app.core.image_assets import IMAGE_SUFFIXES
from app.core.paths import resolve_root_tex
from app.core.project_file_ops import (
    ProjectFileOperationError,
    ProjectPathMove,
    execute_project_path_move,
    find_move_blockers,
    plan_project_path_move,
    remap_moved_path,
    rename_destination,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.core.compiler import CompileManager
    from app.gui.main_window import MainWindow
    from app.gui.main_window_support import EditorTab


class ProjectFileController(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window

    def install_drop_targets(self) -> None:
        for widget in (
            self.window.source_stack,
            self.window.welcome_page,
            self.window.editor_tabs,
        ):
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # type: ignore[no-untyped-def]
        if event.type() not in {
            QEvent.Type.DragEnter,
            QEvent.Type.DragMove,
            QEvent.Type.Drop,
        }:
            return super().eventFilter(watched, event)
        paths = self._tex_paths_from_mime(event.mimeData())
        if not paths:
            return super().eventFilter(watched, event)
        if event.type() == QEvent.Type.Drop:
            self.open_dropped_tex_files(paths)
        event.acceptProposedAction()
        return True

    # --- project root and opening -----------------------------------------

    def set_project_root(self, path: str | Path, *, remember: bool = False) -> Path:
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            raise ProjectFileOperationError("项目根目录不可用。")
        window = self.window
        window.selected_project_scope = root
        root_index = window.model.setRootPath(str(root))
        window.tree.setRootIndex(root_index)
        if remember:
            window._remember_recent_project(root)
        window.dependencies.refresh_memberships()
        return root

    def ensure_project_root_for_file(self, path: str | Path) -> None:
        """Choose a root once; opening children must never collapse the tree."""

        window = self.window
        source = Path(path).expanduser().resolve()
        scope = window.selected_project_scope
        if scope is not None:
            # Paths opened from diagnostics or SyncTeX do not get to widen an
            # explicitly selected project boundary.
            return
        resolution = resolve_root_tex(source)
        root = resolution.root.parent if resolution.root is not None else source.parent
        self.set_project_root(root)

    def open_tree_item(self, index: QModelIndex) -> None:
        path = self.path_for_index(index)
        if path is not None and path.is_file() and path.suffix.lower() == ".tex":
            self.window.open_file(path)

    def open_dropped_tex_files(self, paths: list[str]) -> None:
        for raw_path in paths:
            path = Path(raw_path).expanduser().resolve()
            if path.is_file() and path.suffix.lower() == ".tex":
                scope = self.window.selected_project_scope
                if scope is not None and not path.is_relative_to(scope):
                    self.open_in_new_window(path)
                else:
                    self.window.open_file(path)

    def open_in_new_window(self, path: str | Path) -> "MainWindow":
        source = Path(path).expanduser().resolve()
        child = self.window.spawn_window()
        scope = self.window.selected_project_scope
        if scope is not None and source.is_relative_to(scope):
            child.project_files.set_project_root(scope)
        else:
            child.project_files.ensure_project_root_for_file(source)
        child.open_file(source)
        return child

    def path_for_index(self, index: QModelIndex) -> Path | None:
        if not index.isValid():
            return None
        raw = self.window.model.filePath(index)
        return Path(raw).expanduser().resolve() if raw else None

    @staticmethod
    def _tex_paths_from_mime(mime_data) -> list[str]:  # type: ignore[no-untyped-def]
        if not mime_data.hasUrls():
            return []
        paths: list[str] = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() == ".tex":
                paths.append(str(path))
        return paths

    # --- context menu ------------------------------------------------------

    def show_context_menu(self, position: QPoint) -> None:
        window = self.window
        index = window.tree.indexAt(position)
        path = self.path_for_index(index)
        if path is None:
            return
        window.tree.setCurrentIndex(index)
        menu = QMenu(window.tree)
        suffix = path.suffix.lower()
        if path.is_file() and suffix == ".tex":
            menu.addAction("打开", lambda: window.open_file(path))
            menu.addAction("在新窗口打开", lambda: self.open_in_new_window(path))
            menu.addSeparator()
        elif path.is_file() and suffix in IMAGE_SUFFIXES:
            menu.addAction("插入到当前文档", lambda: window.insert_dropped_images([str(path)]))
            menu.addSeparator()

        scope = window.selected_project_scope
        can_mutate = scope is not None and path != scope and path.is_relative_to(scope)
        rename_action = menu.addAction("重命名…", lambda: self.rename_path(path))
        move_action = menu.addAction("移动到…", lambda: self.move_path(path))
        rename_action.setEnabled(can_mutate)
        move_action.setEnabled(can_mutate)
        menu.exec(window.tree.viewport().mapToGlobal(position))

    def rename_path(self, path: Path) -> bool:
        name, accepted = QInputDialog.getText(
            self.window,
            "重命名",
            "新名称：",
            text=path.name,
        )
        if not accepted:
            return False
        try:
            destination = rename_destination(path, name)
        except ProjectFileOperationError as exc:
            QMessageBox.warning(self.window, "无法重命名", str(exc))
            return False
        if path.is_file() and destination.suffix.lower() != path.suffix.lower():
            QMessageBox.warning(self.window, "无法重命名", "为避免改变文件类型，重命名时必须保留原扩展名。")
            return False
        return self.perform_move(path, destination, operation_label="重命名")

    def move_path(self, path: Path) -> bool:
        scope = self.window.selected_project_scope
        if scope is None:
            return False
        directory = QFileDialog.getExistingDirectory(
            self.window,
            "选择项目内的目标文件夹",
            str(scope),
        )
        if not directory:
            return False
        return self.perform_move(path, Path(directory) / path.name, operation_label="移动")

    # --- guarded mutation --------------------------------------------------

    def perform_move(
        self,
        source: str | Path,
        destination: str | Path,
        *,
        operation_label: str = "移动",
    ) -> bool:
        window = self.window
        scope = window.selected_project_scope
        if scope is None:
            QMessageBox.warning(window, f"无法{operation_label}", "请先打开项目文件夹。")
            return False
        try:
            plan = plan_project_path_move(scope, source, destination)
            overrides = {
                tab.path: tab.editor.toPlainText()
                for tab in window.tabs.values()
                if tab.path is not None and tab.path.suffix.lower() == ".tex"
            }
            blockers = find_move_blockers(plan, text_overrides=overrides)
        except ProjectFileOperationError as exc:
            QMessageBox.warning(window, f"无法{operation_label}", str(exc))
            return False
        if blockers:
            details = []
            for blocker in blockers[:6]:
                try:
                    owner = blocker.owner.relative_to(plan.project_root).as_posix()
                except ValueError:
                    owner = blocker.owner.name
                details.append(
                    f"{owner}:{blocker.line}  \\{blocker.command}{{{blocker.raw_target}}}"
                )
            if len(blockers) > 6:
                details.append(f"另有 {len(blockers) - 6} 处")
            QMessageBox.warning(
                window,
                f"无法安全{operation_label}",
                "该操作会使 LaTeX 相对引用失效。ICSTeX 未改动任何文件：\n\n"
                + "\n".join(details),
            )
            return False

        affected_tabs = self._affected_tabs(plan)
        impacted_managers, manager_tabs = self._impacted_managers(plan, affected_tabs)
        if any(manager.is_busy for manager in impacted_managers):
            QMessageBox.warning(
                window,
                f"无法{operation_label}",
                "相关文档正在编译。请先停止编译，等待状态回到空闲后再操作。",
            )
            return False
        watched_paths = [tab.path for tab, _new_path in affected_tabs if tab.path is not None]
        recent_files = tuple(window.app_settings.recent_files())
        for tab, _new_path in affected_tabs:
            window.documents.cancel_save_timer(tab)
        for old_path in watched_paths:
            window.file_watcher.unwatch(old_path)
        for tab in manager_tabs:
            tab.manager = None
        stop_results = [
            window.compile.retire_manager(manager) for manager in impacted_managers
        ]
        managers_stopped = all(stop_results)
        if not managers_stopped:
            for old_path in watched_paths:
                window._watch_file(old_path)
            self._recreate_managers(manager_tabs)
            self._resume_pending_saves(tab for tab, _new_path in affected_tabs)
            QMessageBox.warning(
                window,
                f"无法{operation_label}",
                "相关编译任务尚未完全退出；本次未移动任何文件。",
            )
            return False

        try:
            execute_project_path_move(plan)
        except ProjectFileOperationError as exc:
            for old_path in watched_paths:
                window._watch_file(old_path)
            self._recreate_managers(manager_tabs)
            self._resume_pending_saves(tab for tab, _new_path in affected_tabs)
            QMessageBox.warning(window, f"无法{operation_label}", str(exc))
            return False

        self._discard_compile_state(impacted_managers)
        self._discard_moved_asset_watches(plan)
        self._remap_local_save_state(plan)
        for tab, new_path in affected_tabs:
            tab.path = new_path
            window._set_tab_title(tab)
            window._watch_file(new_path)
        self._recreate_managers(manager_tabs)
        self._resume_pending_saves(tab for tab, _new_path in affected_tabs)
        self._remap_recent_files(plan, recent_files)
        window._invalidate_include_cache()
        window.dependencies.refresh_memberships()
        window._sync_pdf_panel_to_active_root()
        window._sync_compile_indicators_to_active_root()
        window.refresh_project_panels()
        window.update_recent_menu()
        QTimer.singleShot(0, lambda: window.tree.setCurrentIndex(window.model.index(str(plan.destination))))
        window.statusBar().showMessage(
            f"已{operation_label}：{plan.source.name} → {plan.destination.name}",
            5000,
        )
        return True

    def _affected_tabs(self, plan: ProjectPathMove) -> list[tuple["EditorTab", Path]]:
        affected: list[tuple["EditorTab", Path]] = []
        for tab in self.window.tabs.values():
            if tab.path is None:
                continue
            new_path = remap_moved_path(tab.path, plan)
            if new_path is not None:
                affected.append((tab, new_path))
        return affected

    def _impacted_managers(
        self,
        plan: ProjectPathMove,
        affected_tabs: list[tuple["EditorTab", Path]],
    ) -> tuple[list["CompileManager"], list["EditorTab"]]:
        affected_ids = {id(tab) for tab, _new_path in affected_tabs}
        managers: list["CompileManager"] = []
        for manager in self.window.compile_managers.values():
            root_moves = remap_moved_path(manager.root_file, plan) is not None
            tab_moves = any(
                id(tab) in affected_ids and tab.manager is manager
                for tab in self.window.tabs.values()
            )
            if root_moves or tab_moves:
                managers.append(manager)
        manager_ids = {id(manager) for manager in managers}
        tabs = [
            tab
            for tab in self.window.tabs.values()
            if tab.manager is not None and id(tab.manager) in manager_ids
        ]
        return managers, tabs

    def _recreate_managers(self, tabs: list["EditorTab"]) -> None:
        for tab in tabs:
            if tab.path is not None:
                tab.manager = self.window.create_compile_manager(tab.path)

    def _resume_pending_saves(self, tabs: Iterable["EditorTab"]) -> None:
        for tab in tabs:
            if tab.path is not None and (tab.dirty or tab.modified):
                self.window.schedule_save(
                    tab,
                    compile_after_save=tab.pending_compile_after_save,
                )

    def _discard_compile_state(self, managers: list["CompileManager"]) -> None:
        window = self.window
        for manager in managers:
            root = manager.root_file
            window.compile.release_preview_assets(root)
            if hasattr(window, "pdf_export"):
                window.pdf_export.cancel_root(root)
            window.displayed_pdfs.pop(root, None)
            window.pdf_state.clear_build_output(root)
            window.preview_state.clear_build_output(root)
            window.compile_authorized_roots.discard(root)

    def _discard_moved_asset_watches(self, plan: ProjectPathMove) -> None:
        window = self.window
        moved_assets = [
            path
            for path in tuple(window.preview_asset_roots)
            if remap_moved_path(path, plan) is not None
        ]
        for path in moved_assets:
            roots = window.preview_asset_roots.pop(path, set())
            window.file_watcher.unwatch(path)
            for root in roots:
                assets = window.preview_root_assets.get(root)
                if assets is not None:
                    assets.discard(path)
                window.pdf_state.mark_edited(root)
                window.preview_state.mark_edited(root)

    def _remap_local_save_state(self, plan: ProjectPathMove) -> None:
        window = self.window
        for old_path, content in tuple(window.local_save_contents.items()):
            new_path = remap_moved_path(old_path, plan)
            if new_path is None:
                continue
            window.local_save_contents.pop(old_path, None)
            window.local_save_contents[new_path] = content

    def _remap_recent_files(
        self,
        plan: ProjectPathMove,
        recent_files: tuple[Path, ...],
    ) -> None:
        settings = self.window.app_settings
        for old_path in recent_files:
            new_path = remap_moved_path(old_path, plan)
            if new_path is None:
                continue
            settings.remove_recent_file(old_path)
            settings.add_recent_file(new_path)
