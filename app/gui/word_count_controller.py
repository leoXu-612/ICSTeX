"""Bounded, latest-request Word Count with GUI-only snapshot/presentation."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import logging
from pathlib import Path
import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot

from app.core.latex_tools import LaTeXToolchain
from app.core.word_count import WordCountSnapshot, count_project_snapshot, count_text

if TYPE_CHECKING:
    from app.gui.main_window import MainWindow


logger = logging.getLogger(__name__)
_CACHE_LIMIT = 8


@dataclass(frozen=True)
class _Request:
    key: tuple
    root: Path | None
    buffers: tuple[tuple[Path, str], ...]
    text: str
    tools: LaTeXToolchain
    document_name: str


class _Signals(QObject):
    completed = Signal(object, object, str)


def _logical_id(key: tuple) -> object:
    return key[0] if key[0] is not None else key[2][0][1]


def _compute(request: _Request, signals: _Signals) -> None:
    snapshot = None
    error = ""
    try:
        if request.root is None:
            snapshot = WordCountSnapshot(count_text(request.text, toolchain=request.tools))
        else:
            snapshot = count_project_snapshot(request.root, dict(request.buffers), request.tools)
    except Exception:  # noqa: BLE001 - worker failures must not leave a stuck queue
        logger.exception("Word Count worker failed")
        error = "字数统计未完成，请重试。"
    try:
        signals.completed.emit(request, snapshot, error)
    except RuntimeError:
        # QApplication/receiver can have been destroyed during process exit.
        pass


class WordCountController(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self._signals = _Signals()
        self._signals.completed.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.request)
        self._active: _Request | None = None
        self._pending: _Request | None = None
        self._cache: OrderedDict[tuple, WordCountSnapshot] = OrderedDict()
        self._displayed_key: tuple | None = None
        self._closed = False
        self._retry_key: tuple | None = None

    @property
    def is_busy(self) -> bool:
        return self._active is not None or self._pending is not None or self._timer.isActive()

    def _key(self) -> tuple | None:
        tab = self.window.current_tab()
        if tab is None:
            return None
        root = self.window._compile_root_for_tab(tab)
        revisions = []
        for candidate in self.window.tabs.values():
            if candidate is tab or self._belongs(candidate, root):
                revisions.append((str(candidate.path or ""), id(candidate.editor), candidate.editor.document().revision()))
        source_revision = self.window.pdf_state.record_for(root).source_revision if root is not None else 0
        return root, source_revision, tuple(sorted(revisions)), self.window.toolchain

    def _belongs(self, tab, root: Path | None) -> bool:
        return root is not None and (
            self.window._compile_root_for_tab(tab) == root
            or (tab.path is not None and tab.path.resolve() in self.window.dependencies.paths_for(root))
        )

    def schedule(self) -> None:
        if self._closed:
            return
        self._pending = None
        self._timer.start()
        self._mark_pending(self._key())

    def _mark_pending(self, key: tuple | None) -> None:
        view = self.window.word_count_view
        if key is None:
            view.reset("未选择文档")
            self._displayed_key = None
        elif self._displayed_key is not None and _logical_id(self._displayed_key) == _logical_id(key):
            view.set_pending(keep_result=True)
        else:
            view.set_pending(keep_result=False)

    @Slot()
    def request(self, *, force: bool = False) -> None:
        if self._closed:
            return
        self._timer.stop()
        key = self._key()
        if key is None:
            self._pending = None
            self._mark_pending(None)
            return
        cached = self._cache.get(key)
        if not force and cached is not None and cached.is_current():
            self._cache.move_to_end(key)
            self._pending = None
            self._show(key, cached)
            return
        self._cache.pop(key, None)
        self._mark_pending(key)
        if self._active is not None and self._active.key == key:
            self._pending = None
            return
        root = key[0]
        tab = self.window.current_tab()
        assert tab is not None
        buffers = tuple(
            (candidate.path, candidate.editor.toPlainText())
            for candidate in self.window.tabs.values()
            if candidate.path is not None and self._belongs(candidate, root)
        )
        request = _Request(
            key, root, buffers, tab.editor.toPlainText() if root is None else "",
            self.window.toolchain, root.name if root is not None else "未保存文档",
        )
        if self._active is not None:
            self._pending = request
        else:
            self._launch(request)

    def _launch(self, request: _Request) -> None:
        self._active = request
        # No QWidget or controller is captured by the worker. It receives only
        # immutable data and a lifetime-independent signal emitter.
        threading.Thread(target=_compute, args=(request, self._signals), daemon=True,
                         name="icstex-word-count").start()

    @Slot(object, object, str)
    def _finished(self, request: _Request, snapshot: WordCountSnapshot | None, error: str) -> None:
        if self._closed:
            return
        if self._active is not request:
            return
        self._active = None
        current = self._key()
        stable = snapshot is not None and snapshot.is_current()
        if stable:
            self._cache[request.key] = snapshot
            self._cache.move_to_end(request.key)
            while len(self._cache) > _CACHE_LIMIT:
                self._cache.popitem(last=False)
            if current == request.key:
                self._show(request.key, snapshot)
                self._retry_key = None
        elif current == request.key:
            if error:
                self.window.word_count_view.reset(error)
            elif self._retry_key != request.key:
                # Retry once after a concurrent disk edit; continuous external
                # churn must not create an unbounded self-scheduling loop.
                self._retry_key = request.key
                self._timer.start()
            else:
                self.window.word_count_view.set_pending(keep_result=False)
        pending = self._pending
        self._pending = None
        if pending is not None and pending.key == current:
            self._launch(pending)

    def _show(self, key: tuple, snapshot: WordCountSnapshot) -> None:
        tab = self.window.current_tab()
        if tab is None:
            return
        root = key[0]
        modified = any(
            candidate.modified or candidate.dirty or candidate.path is None
            for candidate in self.window.tabs.values()
            if candidate is tab or self._belongs(candidate, root)
        )
        self.window.word_count_view.set_result(
            snapshot.result, root.name if root is not None else "未保存文档", modified,
        )
        self._displayed_key = key

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        self._pending = None
        self._active = None
        self._cache.clear()
        self._signals.completed.disconnect(self._finished)
