"""Explicit read-only source snapshots; one active worker and one latest request."""
from datetime import datetime
import threading

from PySide6.QtCore import QObject, Qt, Signal, Slot

from app.core.blocks.source_registry import SourceCheckCancelled, check_sources


class _Signals(QObject):
    finished = Signal(object, object, str)


def _run(request, cancelled, closed, signals):
    results, error = (), ""
    try:
        project, records = request
        results = check_sources(project, records, cancelled=lambda: cancelled.is_set() or closed.is_set())
    except SourceCheckCancelled:
        error = "已取消检查；没有修改来源或数据。"
    except Exception:
        error = "来源检查未完成，结果未知；请重试。"
    try:
        signals.finished.emit(request, results, error)
    except RuntimeError:
        pass  # QObject receiver/application was destroyed; worker owns no UI.


class SourceStatusController(QObject):
    changed = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.results = ()
        self.checked_at = ""
        self.message = "尚未检查 · 刷新只读状态，不保存、不导入、不联网。"
        self._displayed_key = None
        self._active = None
        self._pending = None
        self._cancelled = None
        self._closed = threading.Event()
        # Capture only the event; late work never touches a destroyed widget.
        self.destroyed.connect(self._closed.set)
        self._signals = _Signals()
        self._signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        session.model_changed.connect(self.reconcile)
        session.compile_state_changed.connect(self._session_lifecycle)

    @property
    def is_busy(self):
        return self._active is not None

    def _key(self):
        return self.session.project_dir, tuple(self.session.sources)

    def _clear(self, message):
        self.results = ()
        self.checked_at = ""
        self._displayed_key = None
        self.message = message

    @Slot()
    def request(self):
        if self._closed.is_set() or self.session._closed:
            return
        request = self._key()
        if request[0] is None:
            self.cancel()
            return
        self._clear("检查中 · 只读，不更新路径、基线或表格数据。")
        if self._active is not None:
            self._cancelled.set()
            self._pending = request
        else:
            self._launch(request)
        self.changed.emit()

    def _launch(self, request):
        self._active = request
        self._cancelled = threading.Event()
        threading.Thread(target=_run, args=(request, self._cancelled, self._closed, self._signals),
                         name="icstex-source-status", daemon=True).start()

    @Slot(object, object, str)
    def _finished(self, request, results, error):
        if request is not self._active:
            return
        cancelled = self._cancelled.is_set()
        self._active = None
        if self._closed.is_set() or self.session._closed:
            return
        if not cancelled and request == self._key():
            if error:
                self._clear(error)
            else:
                self.results = results
                self._displayed_key = request
                self.checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
                self.message = f"检查快照：{self.checked_at} · 外部文件变化后请主动刷新。"
        elif not self._pending and not cancelled:
            self._clear("来源记录已变化，结果未知；请重新检查。")
        pending, self._pending = self._pending, None
        if pending is not None and pending == self._key():
            self._launch(pending)
        self.changed.emit()

    @Slot()
    def reconcile(self):
        if self._closed.is_set():
            return
        expected = self._pending or self._active or self._displayed_key
        if expected is not None and expected != self._key():
            self.cancel()
            self._clear("来源记录已变化，结果未知；请重新检查。")
            self.changed.emit()

    @Slot()
    def cancel(self):
        self._pending = None
        if self._cancelled is not None:
            self._cancelled.set()
        self._clear("已取消检查；没有修改来源或数据。")
        self.changed.emit()

    @Slot()
    def _session_lifecycle(self):
        if self.session._closed:
            self.shutdown()

    def shutdown(self):
        if self._closed.is_set():
            return
        self._closed.set()
        self.cancel()

