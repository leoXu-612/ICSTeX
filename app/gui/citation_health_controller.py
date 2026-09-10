"""One bounded citation worker; the existing editor/project remain authoritative."""
from datetime import datetime
import hashlib
from pathlib import Path
import threading
from types import SimpleNamespace

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot

from app.core.citation_health import CitationCancelled, CitationRequest, check_citations
from app.core.project_dependencies import MAX_SOURCE_BYTES, read_project_bytes, safe_project_input


class _Signals(QObject):
    finished = Signal(object, object, str)


def _run(request, cancelled, closed, signals):
    report, error = None, ""
    try:
        report = check_citations(request, SimpleNamespace(is_set=lambda: cancelled.is_set() or closed.is_set()))
    except CitationCancelled:
        error = "已取消引用检查；没有保存、编译或修改项目。"
    except Exception:
        error = "引用检查未完成，结果未知；请重试。"
    try:
        signals.finished.emit(request, report, error)
    except RuntimeError:
        pass


class CitationHealthController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._closed = threading.Event()
        self.destroyed.connect(self._closed.set)
        self._active = None
        self._pending = None
        self._cancelled = None
        self._root = self._scope = None
        self._report = None
        self._displayed_key = None
        self._navigating = False
        self._signals = _Signals()
        self._signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.reconcile)

    @property
    def is_busy(self):
        return self._active is not None

    def _key(self):
        window = self.window
        return (window.selected_project_scope, self._root, id(window.current_tab()),
                window.block_mode_action.isChecked(),
                tuple((tab.path, id(tab.editor), tab.editor.document().revision(), tab.modified,
                       tab.dirty, tab.external_conflict) for tab in window.tabs.values()),
                window.dependencies.generation_for(self._root) if self._root else 0)

    @Slot()
    def request(self):
        if self._closed.is_set():
            return
        window = self.window
        panel = window.references_panel
        panel.reference_tabs.setCurrentIndex(1)
        tab = window.current_tab()
        if window.block_mode_action.isChecked() or tab is None or tab.path is None:
            self._invalidate("请先打开普通 LaTeX 项目的源码入口；Block 来源请使用“来源”页。")
            return
        if (tab.path.suffix.lower() == ".bib" and self._report is not None
                and tab.path in self._report.watched_paths):
            root = self._root  # Deliberate report navigation retains its labelled root.
        else:
            root = window._compile_root_for_tab(tab)
        if root is None or root.suffix.lower() not in {".tex", ".ltx"}:
            self._invalidate("未确定 LaTeX 编译入口；请切回主文件后检查。")
            return
        self._root = root
        self._scope = window.selected_project_scope or root.parent
        request = CitationRequest(self._key(), self._scope, root,
                                  tuple((candidate.path, candidate.editor.toPlainText())
                                        for candidate in window.tabs.values() if candidate.path
                                        and candidate.path.is_relative_to(self._scope)))
        self._report = self._displayed_key = None
        panel.set_check_pending("检查中 · 只读，不保存、不编译、不联网。", busy=True)
        self._timer.start()
        if self._active is not None:
            self._cancelled.set()
            self._pending = request
        else:
            self._launch(request)

    def _launch(self, request):
        self._active = request
        self._cancelled = threading.Event()
        threading.Thread(target=_run, args=(request, self._cancelled, self._closed, self._signals),
                         name="icstex-citation-health", daemon=True).start()

    @Slot(object, object, str)
    def _finished(self, request, report, error):
        if request is not self._active:
            return
        cancelled = self._cancelled.is_set()
        self._active = None
        if self._closed.is_set():
            return
        if not cancelled and request.key == self._key():
            if report is not None and report.stable:
                self._report = report
                self._displayed_key = request.key
                label = request.root.relative_to(request.scope).as_posix()
                timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
                self.window.references_panel.set_citation_report(report, request.scope, f"{timestamp} · {label}")
                self.window.file_watcher.set_paths(("citations", id(self)), set(report.watched_paths), canonical=True)
            else:
                self.window.references_panel.set_check_pending(error or "输入在检查期间变化，结果未知；请重新检查。")
        pending, self._pending = self._pending, None
        if pending is not None and pending.key == self._key():
            self._launch(pending)
        elif not cancelled and request.key != self._key():
            self._invalidate("入口或缓冲区已变化；旧引用检查已作废。")

    @Slot()
    def reconcile(self):
        expected = self._pending.key if self._pending else self._active.key if self._active else self._displayed_key
        if expected is not None and expected != self._key():
            self.invalidate()

    def _invalidate(self, message):
        self._pending = self._report = self._displayed_key = None
        if self._cancelled is not None:
            self._cancelled.set()
        self._timer.stop()
        self.window.references_panel.set_check_pending(message)
        self.window.file_watcher.set_paths(("citations", id(self)), set(), canonical=True)

    @Slot()
    def invalidate(self):
        if not self._closed.is_set() and not self._navigating and (self._report is not None or self.is_busy):
            self._invalidate("入口、缓冲区或模式已变化；旧引用检查已作废。")

    @Slot(str)
    def external_changed(self, path):
        if not self._closed.is_set() and self._scope is not None and Path(path).is_relative_to(self._scope):
            self._invalidate("外部输入已变化；请重新检查引用。")

    @Slot()
    def cancel(self):
        if not self._closed.is_set():
            self._invalidate("已取消引用检查；没有保存、编译或修改项目。")

    @Slot(int, int)
    def navigate(self, row, index):
        report = self._report
        if report is None or self._displayed_key != self._key():
            self.invalidate()
            return
        if not 0 <= row < len(report.items) or not 0 <= index < len(report.items[row].locations):
            return
        location = report.items[row].locations[index]
        path = safe_project_input(self._scope, location.path)
        observation = next(((kind, digest) for observed, kind, digest in report.inputs if observed == path), None)
        if path is None or observation is None:
            self.window.references_panel.check_detail.appendPlainText("该位置缺失或未安全读取；请选择关联源码位置。")
            return
        kind, digest = observation
        tab = self.window._tab_for_path(path)
        try:
            if kind == "buffer":
                payload = tab.editor.toPlainText().encode("utf-8") if tab is not None else b""
            else:
                payload = read_project_bytes(path, self._scope, max_bytes=MAX_SOURCE_BYTES)
            if hashlib.sha256(payload).hexdigest() != digest:
                self._invalidate("定位内容已变化；请刷新后使用新的行号。")
                return
        except OSError:
            self._invalidate("定位文件不可读；结果未知。")
            return
        self._navigating = True
        try:
            self.window.open_file(path, location.line)
        finally:
            self._navigating = False
        # Rebind only this deliberate, content-checked navigation, not arbitrary
        # tab changes or an external event received while opening the location.
        if self._report is report:
            self._displayed_key = self._key()

    def shutdown(self):
        if self._closed.is_set():
            return
        self._closed.set()
        self._invalidate("引用检查已关闭。")
