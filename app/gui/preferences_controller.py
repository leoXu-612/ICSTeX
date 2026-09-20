"""Preferences, recent files/projects, toolbox visibility, and editor-option sync.

Holds the back-reference to MainWindow so it can poke checkable actions and
push QSettings updates through ``app_settings``.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QMessageBox

from app.core.paths import find_root_tex
from app.core.settings import AppPreferences
from app.core.latex_tools import detect_toolchain
from app.gui.latex_editor import LaTeXEditor
from app.gui.main_window_actions import auto_compile_tooltip, auto_compile_label
from app.gui.main_window_support import set_dynamic_property
from app.gui.settings_dialog import SettingsDialog

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.gui.main_window import MainWindow


_INTERNAL_PROJECT_DIRS = frozenset({".icstex", ".latex_build"})


class PreferencesController:
    def __init__(self, window: "MainWindow") -> None:
        self.window = window
        self._recent_menu_key: tuple[tuple[Path, ...], tuple[Path, ...]] | None = None

    # --- toolbox / auto-compile sync ---------------------------------------

    def set_toolbox_visible(self, visible: bool) -> None:
        window = self.window
        if not hasattr(window, "toolbox_dock"):
            return
        if hasattr(window, "source_panels"):
            window.source_panels.set_toolbox(visible)
            return
        window.toolbox_dock.setVisible(visible)

    def sync_toolbox_action(self, visible: bool) -> None:
        action = self.window.toolbox_action
        if action.isChecked() == visible:
            return
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)

    def sync_auto_compile_action(self, enabled: bool) -> None:
        self._update_auto_compile_status(enabled)
        action = self.window.auto_compile_action
        if action.isChecked() == enabled:
            return
        action.setChecked(enabled)

    def sync_auto_compile_toggle(self, enabled: bool) -> None:
        self._update_auto_compile_status(enabled)
        toggle = self.window.auto_compile_toggle
        if toggle.isChecked() == enabled:
            return
        with QSignalBlocker(toggle):
            toggle.setChecked(enabled)

    def _update_auto_compile_status(self, enabled: bool) -> None:
        label = getattr(self.window, "status_auto_label", None)
        if label is None:
            return
        label.setText(auto_compile_label(self.window.preferences.fast_preview) if enabled else "手动编译")
        label.setToolTip(auto_compile_tooltip(self.window.preferences.fast_preview))
        set_dynamic_property(label, "state", "active" if enabled else "idle")

    # --- welcome page status -----------------------------------------------

    def update_welcome_page(self) -> None:
        self.update_welcome_environment()
        if hasattr(self.window, "welcome_page"):
            files, projects = self._recent_paths()
            self.window.welcome_page.set_recent_projects(projects, recent_files=files)

    def update_welcome_environment(self) -> None:
        """Refresh environment text independently of recent-file presentation."""
        window = self.window
        if not hasattr(window, "welcome_page"):
            return
        if window.toolchain.is_compile_ready:
            message = (
                f"{window.toolchain.compiler_name} 可用 · "
                f"默认引擎 {window.current_engine.display_name}"
            )
            window.welcome_page.set_toolchain_status(True, message)
        else:
            window.welcome_page.set_toolchain_status(False, window.toolchain.missing_compile_message)

    def recheck_environment(self) -> None:
        # Explicit welcome-page action. Reuse detection; never compile or rebuild
        # active managers just to update this information.
        self.window.toolchain = detect_toolchain()
        self.update_welcome_environment()

    # --- settings dialog & preference application --------------------------

    def show_settings_dialog(self) -> None:
        window = self.window
        dialog = SettingsDialog(window.preferences, window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.apply_preferences(dialog.values(), save=True)
        window.statusBar().showMessage("设置已保存。", 4000)

    def apply_preferences(self, preferences: AppPreferences, *, save: bool = False) -> None:
        """GUI-thread batch: publish complete options before applying or persisting.

        Direct user toggles retain their slots; only these programmatic assignments
        are blocked. A settings batch changes compile configuration, not build consent.
        """
        window = self.window
        previous_engine = window.current_engine
        previous_compile_delay = window.compile_debounce_ms
        window.preferences = preferences
        window.save_debounce_ms = preferences.save_debounce_ms
        window.compile_debounce_ms = preferences.compile_debounce_ms

        for control, value in (
            (window.auto_compile_action, preferences.auto_compile),
            (window.auto_compile_toggle, preferences.auto_compile),
            (window.auto_item_action, preferences.auto_item),
            (window.auto_environment_action, preferences.auto_environment),
            (window.auto_pairs_action, preferences.auto_pairs),
            (window.snippets_action, preferences.snippets),
        ):
            with QSignalBlocker(control):
                control.setChecked(value)
        self._update_auto_compile_status(preferences.auto_compile)
        tooltip = auto_compile_tooltip(preferences.fast_preview)
        window.auto_compile_action.setText(auto_compile_label(preferences.fast_preview))
        window.auto_compile_toggle.set_mode_text(window.auto_compile_action.text())
        window.auto_compile_action.setToolTip(tooltip)
        window.auto_compile_toggle.setToolTip(tooltip)

        for tab in window.tabs.values():
            window.documents.apply_editor_font(tab.editor)
            self.apply_editor_options(tab.editor)

        if preferences.default_engine != previous_engine:
            window.compile.set_engine(preferences.default_engine, compile_after=False, persist=False)
        elif previous_compile_delay != window.compile_debounce_ms:
            window.compile.rebuild_managers()

        if save:
            window.app_settings.save_preferences(preferences)

    def preferences_from_ui(self) -> AppPreferences:
        window = self.window
        return replace(
            window.preferences,
            default_engine=window.current_engine,
            auto_compile=window.auto_compile_action.isChecked(),
            auto_item=window.auto_item_action.isChecked(),
            auto_environment=window.auto_environment_action.isChecked(),
            auto_pairs=window.auto_pairs_action.isChecked(),
            snippets=window.snippets_action.isChecked(),
        )

    def persist_preferences_from_ui(self) -> None:
        window = self.window
        window.preferences = self.preferences_from_ui()
        window.app_settings.save_preferences(window.preferences)

    # --- recent files / projects -------------------------------------------

    def _recent_paths(self) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
        """Read current records/existence; presentation caches never authorize opening."""
        settings = self.window.app_settings
        return (tuple(path for path in settings.recent_files() if path.is_file()),
                tuple(path for path in settings.recent_projects() if _is_displayable_project(path)))

    def update_recent_menu(self) -> None:
        window = self.window
        recent_files, recent_projects = key = self._recent_paths()
        if hasattr(window, "welcome_page"):
            window.welcome_page.set_recent_projects(recent_projects, recent_files=recent_files)
        if key == self._recent_menu_key:
            return
        self._recent_menu_key = key
        window.recent_menu.clear()

        if recent_files:
            files_menu = window.recent_menu.addMenu("文件")
            for path in recent_files:
                action = QAction(path.name, window)
                action.setToolTip(str(path))
                action.triggered.connect(lambda _checked=False, item=path: self.open_recent_file(item))
                files_menu.addAction(action)

        if recent_projects:
            projects_menu = window.recent_menu.addMenu("项目")
            for path in recent_projects:
                action = QAction(path.name, window)
                action.setToolTip(str(path))
                action.triggered.connect(lambda _checked=False, item=path: self.open_recent_project(item))
                projects_menu.addAction(action)

        if not recent_files and not recent_projects:
            empty = QAction("暂无最近打开", window)
            empty.setEnabled(False)
            window.recent_menu.addAction(empty)

    def open_recent_file(self, path: Path) -> None:
        window = self.window
        if not path.exists():
            window.app_settings.remove_recent_file(path)
            self.update_recent_menu()
            QMessageBox.warning(window, "最近文件不可用", f"这个文件已经不存在：\n{path}")
            return
        window.selected_project_scope = None
        window.open_file(path)

    def open_recent_project(self, path: Path) -> None:
        window = self.window
        if not path.exists() or not path.is_dir():
            window.app_settings.remove_recent_project(path)
            self.update_recent_menu()
            QMessageBox.warning(window, "最近项目不可用", f"这个项目文件夹已经不存在：\n{path}")
            return
        window.project_files.set_project_root(path, remember=True)
        candidate = find_root_tex(path)
        if candidate:
            window.open_file(candidate)
        else:
            window.statusBar().showMessage(f"已打开项目文件夹：{path.name}。未自动找到 root .tex。", 5000)

    def remember_recent_file(self, path: Path) -> None:
        window = self.window
        window.app_settings.add_recent_file(path)
        window.app_settings.add_recent_project(_project_root_for_recent_file(path))
        self.update_recent_menu()

    def remember_recent_project(self, path: Path) -> None:
        window = self.window
        window.app_settings.add_recent_project(path)
        self.update_recent_menu()

    # --- editor options sync -----------------------------------------------

    def apply_editor_options(self, editor: LaTeXEditor) -> None:
        window = self.window
        editor.auto_item_enabled = window.auto_item_action.isChecked()
        editor.auto_environment_enabled = window.auto_environment_action.isChecked()
        editor.auto_pairs_enabled = window.auto_pairs_action.isChecked()
        editor.snippets_enabled = window.snippets_action.isChecked()
        editor.set_soft_wrap_enabled(window.preferences.soft_wrap)

    def apply_editor_options_to_all(self) -> None:
        for tab in self.window.tabs.values():
            self.apply_editor_options(tab.editor)


def _is_displayable_project(path: Path) -> bool:
    return path.is_dir() and not any(part in _INTERNAL_PROJECT_DIRS for part in path.parts)


def _project_root_for_recent_file(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    for parent in resolved.parents:
        if parent.name in _INTERNAL_PROJECT_DIRS:
            return parent.parent
    root_file = find_root_tex(resolved)
    return root_file.parent if root_file is not None else resolved.parent
