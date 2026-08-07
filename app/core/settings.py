from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings

from app.core.latex_tools import LaTeXEngine


MAX_RECENT_ITEMS = 10


@dataclass(frozen=True)
class AppPreferences:
    default_engine: LaTeXEngine = LaTeXEngine.AUTO
    auto_compile: bool = True
    fast_preview: bool = True
    save_debounce_ms: int = 800
    compile_debounce_ms: int = 1200
    editor_font_size: int = 13
    auto_item: bool = True
    auto_environment: bool = True
    auto_pairs: bool = True
    snippets: bool = True
    soft_wrap: bool = True
    ui_scale: float = 1.0
    density: str = "comfortable"


class AppSettings:
    def __init__(self, settings: QSettings | None = None) -> None:
        self.settings = settings or QSettings("ICSTeX", "ICSTeX")

    def load_preferences(self) -> AppPreferences:
        return AppPreferences(
            default_engine=_engine(self.settings.value("editor/default_engine", LaTeXEngine.AUTO.value)),
            auto_compile=_bool(self.settings.value("editor/auto_compile", True)),
            fast_preview=_bool(self.settings.value("compile/fast_preview", True)),
            save_debounce_ms=_int(self.settings.value("editor/save_debounce_ms", 800), 200, 5000),
            compile_debounce_ms=_int(self.settings.value("editor/compile_debounce_ms", 1200), 300, 10000),
            editor_font_size=_int(self.settings.value("editor/font_size", 13), 9, 28),
            auto_item=_bool(self.settings.value("editor/auto_item", True)),
            auto_environment=_bool(self.settings.value("editor/auto_environment", True)),
            auto_pairs=_bool(self.settings.value("editor/auto_pairs", True)),
            snippets=_bool(self.settings.value("editor/snippets", True)),
            soft_wrap=_bool(self.settings.value("editor/soft_wrap", True)),
            ui_scale=_float(self.settings.value("appearance/ui_scale", 1.0), 0.9, 1.5),
            density=_str(self.settings.value("appearance/density", "comfortable")),
        )

    def save_preferences(self, preferences: AppPreferences) -> None:
        self.settings.setValue("editor/default_engine", preferences.default_engine.value)
        self.settings.setValue("editor/auto_compile", preferences.auto_compile)
        self.settings.setValue("compile/fast_preview", preferences.fast_preview)
        self.settings.setValue("editor/save_debounce_ms", preferences.save_debounce_ms)
        self.settings.setValue("editor/compile_debounce_ms", preferences.compile_debounce_ms)
        self.settings.setValue("editor/font_size", preferences.editor_font_size)
        self.settings.setValue("editor/auto_item", preferences.auto_item)
        self.settings.setValue("editor/auto_environment", preferences.auto_environment)
        self.settings.setValue("editor/auto_pairs", preferences.auto_pairs)
        self.settings.setValue("editor/snippets", preferences.snippets)
        self.settings.setValue("editor/soft_wrap", preferences.soft_wrap)
        self.settings.setValue("appearance/ui_scale", preferences.ui_scale)
        self.settings.setValue("appearance/density", preferences.density)
        self.settings.sync()

    def recent_files(self) -> list[Path]:
        return _paths(self.settings.value("recent/files", []))

    def recent_projects(self) -> list[Path]:
        return _paths(self.settings.value("recent/projects", []))

    def add_recent_file(self, path: str | Path) -> None:
        self._add_recent("recent/files", path)

    def add_recent_project(self, path: str | Path) -> None:
        self._add_recent("recent/projects", path)

    def remove_recent_file(self, path: str | Path) -> None:
        self._remove_recent("recent/files", path)

    def remove_recent_project(self, path: str | Path) -> None:
        self._remove_recent("recent/projects", path)

    def _add_recent(self, key: str, path: str | Path) -> None:
        normalized = Path(path).expanduser().resolve()
        values = [item for item in _paths(self.settings.value(key, [])) if item != normalized]
        values.insert(0, normalized)
        self.settings.setValue(key, [str(item) for item in values[:MAX_RECENT_ITEMS]])
        self.settings.sync()

    def _remove_recent(self, key: str, path: str | Path) -> None:
        normalized = Path(path).expanduser().resolve()
        values = [item for item in _paths(self.settings.value(key, [])) if item != normalized]
        self.settings.setValue(key, [str(item) for item in values])
        self.settings.sync()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _int(value: Any, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = low
    return max(low, min(high, number))


def _float(value: Any, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = low
    return max(low, min(high, number))


def _str(value: Any, default: str = "") -> str:
    return str(value) if value is not None else default


def _engine(value: Any) -> LaTeXEngine:
    try:
        return LaTeXEngine(str(value))
    except ValueError:
        return LaTeXEngine.AUTO


def _paths(value: Any) -> list[Path]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = [value]
    else:
        raw_values = list(value)
    paths: list[Path] = []
    for item in raw_values:
        if not item:
            continue
        paths.append(Path(str(item)).expanduser().resolve())
    return paths
