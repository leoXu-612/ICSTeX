"""One bounded worker per window; no new writer or authoritative session model."""
from __future__ import annotations

from dataclasses import replace
import json
import logging
from pathlib import Path
import threading
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import QDockWidget

from app.core.block_submission import BlockCheckInput
from app.core.blocks.model import SCHEMA_VERSION
from app.core.latex_tools import LaTeXEngine
from app.core.project_dependencies import safe_project_input
from app.core.project_profile import PROFILE_PATH
from app.core.submission_check import (BufferInput, CheckCancelled, CheckRequest,
                                       check_submission)

if TYPE_CHECKING:
    from app.gui.main_window import MainWindow


class _Signals(QObject):
    finished = Signal(object, object, str)


def _run(request, cancelled, signals):
    report, error = None, ""
    try:
        report = check_submission(request, cancelled)
    except CheckCancelled:
        error = "已取消检查；没有保存、编译或修改项目。"
    except Exception:
        logging.getLogger(__name__).exception("Submission check failed")
        error = "检查未完成，结果未知。请重新检查或打开环境医生。"
    try:
        signals.finished.emit(request, report, error)
    except RuntimeError:
        pass  # Receiver/application destroyed; worker holds no QWidget.


class SubmissionCheckController(QObject):
    def __init__(self, window: "MainWindow"):
        super().__init__(window)
        self.window = window
        self._closed = False
        self._active = None
        self._pending = None
        self._cancelled = None
        self._displayed_key = None
        self._root = None
        self._block_dock = QDockWidget("提交检查", window)
        self._block_dock.setObjectName("submissionCheckDock")
        window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._block_dock)
        self._block_dock.hide()
        self._signals = _Signals()
        self._signals.finished.connect(self._finished, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.reconcile)
        # This timer checks only existing revision/configuration fields, not files.

    @property
    def is_busy(self):
        return self._active is not None

    def _active_block(self):
        action = getattr(self.window, "block_mode_action", None)
        return getattr(self.window, "block_session", None) if action and action.isChecked() else None

    def _context(self):
        window = self.window
        session = self._active_block()
        if session is not None:
            scope = session.project_dir
            root = scope / "main.tex" if scope else None
            tabs = tuple(tab for tab in window.tabs.values()
                         if scope and tab.path and tab.path.is_relative_to(scope))
            return self._quick_key(root), scope, root, tabs, None, session
        tab = window.current_tab()
        root = window._compile_root_for_tab(tab)
        scope = window.selected_project_scope or (root.parent if root else None)
        paths = window.dependencies.paths_for(root) if root else frozenset()
        tabs = tuple(candidate for candidate in window.tabs.values()
                     if candidate is tab or (root is not None and
                     (window._compile_root_for_tab(candidate) == root or candidate.path in paths)))
        record = window.pdf_state.record_for(root) if root else None
        key = self._quick_key(root)
        return key, scope, root, tabs, record, None

    def _quick_key(self, root):
        window = self.window
        active = self._active_block()
        if active:
            manager = active.compile_manager
            return ("block", id(active), active.project_dir, root, active._revision, active.editor_draft_revision,
                    tuple((tab.path, id(tab.editor), tab.editor.document().revision(),
                           tab.modified, tab.dirty) for tab in window.tabs.values()
                          if active.project_dir and tab.path and tab.path.is_relative_to(active.project_dir)),
                    manager.engine if manager else LaTeXEngine.XELATEX,
                    manager.toolchain if manager else window.toolchain, active.compile_generation)
        session = getattr(window, "block_session", None)
        return (window.selected_project_scope, root, id(window.current_tab()),
                tuple((tab.path, id(tab.editor), tab.editor.document().revision(),
                       tab.modified, tab.dirty) for tab in window.tabs.values()),
                repr(window.pdf_state.record_for(root)) if root else None,
                window.current_engine, window.toolchain,
                window.dependencies.generation_for(root) if root else 0,
                (id(session), session._revision, session._pending_save_reason) if session else None,
                bool(self._active_block()),
                (session.compile_manager.engine, session.compile_manager.toolchain)
                if session and session.compile_manager else None)

    def _key(self):
        return self._quick_key(self._root)

    @Slot()
    def show(self):
        window = self.window
        self.mode_changed()
        if self._active_block():
            window.tabifyDockWidget(window.block_diagnostics_dock, self._block_dock)
            self._block_dock.show()
            self._block_dock.raise_()
            self.request()
            return
        window.bottom_tabs.setCurrentWidget(window.submission_panel)
        sizes = window.vertical_splitter.sizes()
        if sizes and sizes[-1] < 180:
            window.vertical_splitter.setSizes([max(220, window.height() - 300), 260])
        self.request()

    @Slot()
    def mode_changed(self):
        self.invalidate()
        self.window.file_watcher.set_paths(("submission", id(self)), set(), canonical=True)
        self.window.file_watcher.set_paths(("profile", id(self)), set(), canonical=True)
        panel = self.window.submission_panel
        tabs = self.window.bottom_tabs
        if self._active_block():
            index = tabs.indexOf(panel)
            if index >= 0:
                tabs.removeTab(index)
                self._block_dock.setWidget(panel)
        elif self._block_dock.widget() is panel:
            self._block_dock.hide()
            panel.setParent(self.window)
            self._block_dock.setWidget(None)
            tabs.addTab(panel, "提交检查")

    @staticmethod
    def _block_input(session):
        if session is None:
            return None
        blocks = [block.to_dict() for block in session.registry.blocks()]
        # Only applied registry contents are build inputs. Editor drafts are
        # reported separately and cannot replace an arbitrary table here.
        return BlockCheckInput(
            json.dumps({"format": "icstex-blocks", "schemaVersion": SCHEMA_VERSION, "blocks": blocks}),
            json.dumps({"schemaVersion": "1.0.0", "layouts": [session.layout.to_dict()] if session.layout else []}),
            json.dumps({"sources": [source.to_dict() for source in session.sources]}),
            json.dumps(session.document_theme.to_dict()),
            getattr(session, "_raw_latex_authorized", False),
            tuple(draft.label for draft in session.editor_drafts.values()),
        )

    @Slot()
    def request(self):
        if self._closed:
            return
        key, scope, root, tabs, record, session = self._context()
        self.window.file_watcher.set_paths(
            ("profile", id(self)), {scope / PROFILE_PATH} if scope else set(),
            canonical=True, project_profile=True)
        self._root = root
        tab = self.window.current_tab()
        engine = (self.window.compile._effective_engine_for(tab.path, root)
                  if tab is not None and tab.path is not None and root is not None
                  else self.window.current_engine)
        tools = self.window.toolchain
        if session:
            engine = session.compile_manager.engine if session.compile_manager else LaTeXEngine.XELATEX
            tools = session.compile_manager.toolchain if session.compile_manager else tools
        evidence = session.final_evidence if session else self.window.compile.final_evidence_for(root)
        extra_inputs = set(self.window.dependencies.paths_for(root)) if root else set()
        if evidence and evidence.inputs:
            extra_inputs.update(path for path, _ in evidence.inputs.observations)
        request = CheckRequest(
            key, scope, root,
            tuple(BufferInput(tab.path, tab.editor.toPlainText(), tab.editor.document().revision(),
                              tab.modified or tab.dirty) for tab in tabs),
            tools, engine,
            replace(record) if record is not None else None,
            tuple(sorted(extra_inputs)),
            block=self._block_input(session),
            baseline_observations=self.window.dependencies.observations_for(root) if root else (),
            build_evidence=evidence,
            source_revision=session._revision if session else record.source_revision if record else None,
            building=session.final_is_running if session else False,
        )
        self._displayed_key = None
        self.window.submission_panel.pending("检查中 · 只读，不保存、不编译、不联网。", busy=True)
        self._timer.start()
        if self._active is not None:
            self._cancelled.set()
            self._pending = request
        else:
            self._launch(request)

    def _launch(self, request):
        self._active = request
        self._cancelled = threading.Event()
        threading.Thread(target=_run, args=(request, self._cancelled, self._signals),
                         name="icstex-submission-check", daemon=True).start()

    @Slot(object, object, str)
    def _finished(self, request, report, error):
        if self._closed or request is not self._active:
            return
        cancelled = self._cancelled.is_set()
        self._active = None
        if not cancelled and request.key == self._key():
            if report is not None and report.stable:
                self.window.submission_panel.set_report(report)
                self._displayed_key = request.key
                self.window.file_watcher.set_paths(
                    ("submission", id(self)), set(report.watched_paths), canonical=True,
                    block_metadata=request.block is not None, project_profile=True)
            else:
                self.window.submission_panel.pending(error or "输入在检查期间变化，结果未知；请重新检查。")
        elif self._pending is None:
            self.window.submission_panel.pending("输入已变化或检查已取消；请重新检查。")
        pending, self._pending = self._pending, None
        if pending is not None and pending.key == self._key():
            self._launch(pending)
        self.window.workspace.schedule()

    @Slot()
    def reconcile(self):
        if self._closed:
            return
        expected = self._displayed_key or (self._active.key if self._active else None)
        if expected is not None and expected != self._key():
            self.invalidate()

    @Slot()
    def invalidate(self):
        if self._closed:
            return
        if hasattr(self.window, "workspace"):
            self.window.workspace.schedule()
        had_result = self._displayed_key is not None or self._active is not None
        self._displayed_key = None
        self._pending = None
        if self._cancelled is not None:
            self._cancelled.set()
        if had_result:
            self.window.submission_panel.pending("输入或构建状态已变化 · 待重新检查。")
        self._timer.stop()

    @Slot(str)
    def external_changed(self, path):
        if self._closed:
            return
        session = self._active_block()
        scope = session.project_dir if session else (self.window.selected_project_scope or
                                                     (self._root.parent if self._root else None))
        if scope is not None and Path(path).is_relative_to(scope):
            self.invalidate()

    @Slot(str, int)
    def build_started(self, root, _build_id):
        if Path(root) == self._root:
            self.invalidate()

    @Slot(object)
    def build_finished(self, result):
        if result.root_file == self._root:
            self.invalidate()

    @Slot()
    def cancel(self):
        self.invalidate()
        self.window.submission_panel.pending("已取消检查；没有保存、编译或修改项目。")

    @Slot(int)
    def act(self, index):
        report = self.window.submission_panel.report
        if report is None or self._displayed_key != self._key():
            self.invalidate()
            return
        if not 0 <= index < len(report.items):
            return
        item = report.items[index]
        _, scope, root, _, _, session = self._context()
        if item.action == "navigate" and scope and item.file:
            path = safe_project_input(scope, item.file)
            if path is not None and path.is_file():
                if session:
                    from app.gui.block_mode import _set_block_mode
                    _set_block_mode(self.window, False)
                self.window.open_file(path, item.line or 1)
        elif item.action == "save":
            if session:
                session.save_now()
            elif root is None:
                self.window.save_current()
            else:
                self.window.documents.flush_root_documents(root)
            self.invalidate()
        elif item.action == "compile":
            if session:
                session.compile_final()
            else:
                self.window.compile_action.trigger()
            self.invalidate()
        elif item.action == "environment":
            self.window.show_environment_doctor()
        elif item.action == "profile":
            self.window.project_profile_action.trigger()
        elif item.action == "word_count":
            if session:
                # The selected row already exposes captured generated-source count.
                self.window.submission_panel.detail.setFocus()
                return
            self.window.bottom_tabs.setCurrentWidget(self.window.word_count_panel)
            self.window.update_word_count(force=True)

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        if hasattr(self.window, "workspace"):
            self.window.workspace.shutdown()
        self._timer.stop()
        if self._cancelled is not None:
            self._cancelled.set()
        self._pending = None
        self._signals.finished.disconnect(self._finished)
        self.window.file_watcher.set_paths(("submission", id(self)), set(), canonical=True)
        self.window.file_watcher.set_paths(("profile", id(self)), set(), canonical=True)
