from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

from app.core.compiler import BuildPurpose, CompileOutcome, CompileResult
from app.core.latex_tools import LaTeXToolchain
from app.core.pdf_state import PdfFreshness
from app.core.project_dependencies import observe_input, read_recorder_dependencies
from app.core.settings import AppSettings
from app.gui.main_window import MainWindow


def wait_until(predicate, timeout: float = 4) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class GuiDependencyTests(TestCase):
    def setUp(self) -> None:
        self.app = QApplication.instance() or QApplication([])
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / "main.tex"
        self.child = self.root / "child.tex"
        self.bib = self.root / "refs.bib"
        self.source.write_text(
            "\\documentclass{article}\n\\bibliography{refs}\n"
            "\\begin{document}Root \\input{child}\\end{document}\n",
            encoding="utf-8",
        )
        self.child.write_text("one", encoding="utf-8")
        self.bib.write_text("@book{first,title={First}}", encoding="utf-8")
        settings = AppSettings(QSettings(str(self.root / "settings.ini"), QSettings.Format.IniFormat))
        self.window = MainWindow(settings_store=settings)
        self.window.toolchain = LaTeXToolchain(None, None)
        self.window.auto_compile_action.setChecked(False)
        self.window.save_debounce_ms = 60_000
        # Real directory restoration is covered by test_file_watcher. Here
        # inject events deterministically while retaining actual registrations.
        self.window.file_watcher._on_change = lambda _path: None
        self.window.open_file(self.source)
        self.tab = self.window.current_tab()
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))

    def tearDown(self) -> None:
        for tab in self.window.tabs.values():
            tab.dirty = tab.modified = False
        self.window.close()
        self.tmp.cleanup()

    def _manager(self, tab=None):
        selected = tab or self.tab
        selected.manager = self.window.create_compile_manager(selected.path)
        return selected.manager

    def _current_pdf(self, manager) -> None:
        manager.output_dir.mkdir(exist_ok=True)
        manager.pdf_file.write_bytes(b"%PDF-1.4 retained")
        self.window.pdf_state.begin_build(manager.root_file, 1)
        self.window.pdf_state.finish_build(
            manager.root_file, 1, CompileOutcome.SUCCESS, pdf_file=manager.pdf_file,
        )

    def _event(self, path: Path) -> None:
        self.window.reload_external_change(str(path))
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))

    def test_open_registers_unopened_inputs_without_compilation_authority(self) -> None:
        self.assertIsNone(self.tab.manager)
        self.assertFalse(self.window.compile_authorized_roots)
        self.assertTrue({self.source, self.child, self.bib}.issubset(self.window.file_watcher._files))
        self.assertIn(self.root / "article.cls", self.window.file_watcher._files)
        self.assertFalse(any(".latex_build" in path.parts for path in self.window.file_watcher._files))

    def test_unopened_same_size_edit_updates_stale_state_and_word_count_with_auto_off(self) -> None:
        manager = self._manager()
        self._current_pdf(manager)
        self.window.compile_authorized_roots.add(manager.root_file)
        self.window.update_word_count()
        self.assertTrue(wait_until(lambda: not self.window.word_counts.is_busy))
        self.assertEqual(self.window.word_count_labels["effective"].text(), "2")
        before = self.child.stat()
        self.child.write_text("a b", encoding="utf-8")
        os.utime(self.child, ns=(before.st_atime_ns, before.st_mtime_ns))
        with patch.object(manager, "schedule_compile") as compile_request:
            self._event(self.child)
        compile_request.assert_not_called()
        record = self.window.pdf_state.record_for(manager.root_file)
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)
        self.assertEqual(record.source_revision, 1)
        self.assertEqual(self.tab.editor.toPlainText(), self.source.read_text())
        self.assertTrue(wait_until(lambda: not self.window.word_counts.is_busy))
        self.assertEqual(self.window.word_count_labels["effective"].text(), "3")

    def test_same_content_and_duplicate_events_do_not_add_revisions_or_builds(self) -> None:
        manager = self._manager()
        self._current_pdf(manager)
        self.window.auto_compile_action.setChecked(True)
        self.window.compile_authorized_roots.add(manager.root_file)
        with patch.object(manager, "schedule_compile") as compile_request:
            self.child.write_text("one", encoding="utf-8")
            self._event(self.child)
            self.window.dependencies.reconcile()
            self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
            self.assertEqual(self.window.pdf_state.record_for(manager.root_file).source_revision, 0)
            compile_request.assert_not_called()
            self.child.write_text("new content", encoding="utf-8")
            for _ in range(5):
                self.window.reload_external_change(str(self.child))
            self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
            self.assertEqual(compile_request.call_count, 1)
            self.assertEqual(self.window.pdf_state.record_for(manager.root_file).source_revision, 1)

    def test_shared_dependency_uses_each_roots_gate_and_survives_child_close(self) -> None:
        first = self._manager()
        second_path = self.root / "second.tex"
        second_path.write_text("\\documentclass{article}\n\\input{child}", encoding="utf-8")
        self.window.open_file(second_path)
        other = self.window.current_tab()
        second = self._manager(other)
        self.window.open_file(self.child)
        self.window.close_tab(self.window.editor_tabs.currentIndex())
        self.assertIn(self.child, self.window.file_watcher._files)
        self.assertEqual(self.window.dependencies.roots_for(self.child), frozenset({first.root_file, second.root_file}))
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        self.window.auto_compile_action.setChecked(True)
        self.window.compile_authorized_roots.add(first.root_file)
        with patch.object(first, "schedule_compile") as first_request, patch.object(second, "schedule_compile") as second_request:
            self.child.write_text("changed", encoding="utf-8")
            self._event(self.child)
        first_request.assert_called_once_with("输入依赖修改", BuildPurpose.PREVIEW)
        second_request.assert_not_called()
        self.assertEqual(self.window.pdf_state.record_for(first.root_file).source_revision, 1)
        self.assertEqual(self.window.pdf_state.record_for(second.root_file).source_revision, 1)
        self.window.close_tab(self.window._index_for_tab_id(id(self.tab.editor)))
        self.assertIn(self.child, self.window.file_watcher._files)
        self.assertEqual(self.window.dependencies.roots_for(self.child), frozenset({second.root_file}))

    def test_successful_recorder_inputs_are_filtered_and_failed_build_retains_them(self) -> None:
        manager = self._manager()
        self._current_pdf(manager)
        data = self.root / "dynamic.csv"
        data.write_text("x,y\n1,2")
        fls = manager.output_dir / "main.fls"
        fls.write_text("INPUT dynamic.csv\nINPUT result.pdf\nOUTPUT result.pdf\nINPUT .latex_build/main.aux\n")
        snapshot = read_recorder_dependencies(fls, root=manager.root_file, scope=self.root)
        self.assertIsNotNone(snapshot)
        result = CompileResult(
            root_file=manager.root_file, output_dir=manager.output_dir,
            pdf_file=manager.pdf_file, log_file=manager.log_file, command=[],
            returncode=0, stdout="", stderr="", duration_seconds=0.1,
            outcome=CompileOutcome.SUCCESS,
            recorder_inputs=tuple(snapshot.paths),
        )
        # The next build may already have overwritten FLS before Qt consumes
        # the result. Only its immutable worker-captured inputs are authoritative.
        fls.write_text("INPUT replacement.csv\n")
        self.window.dependencies.accept_build(result)
        self.assertIn(data, self.window.file_watcher._files)
        self.assertNotIn(self.root / "result.pdf", self.window.file_watcher._files)
        fls.write_text("INPUT replacement.csv\n")
        self.window.dependencies.accept_build(replace(result, outcome=CompileOutcome.LATEX_ERROR))
        self.assertIn(data, self.window.file_watcher._files)
        self.assertNotIn(self.root / "replacement.csv", self.window.file_watcher._files)
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        data.unlink()
        self._event(data)
        self.assertIn(data, self.window.file_watcher._files)
        data.write_text("x,y\n3,4")
        self._event(data)
        self.assertEqual(self.window.pdf_state.record_for(manager.root_file).source_revision, 2)

    def test_missed_unopened_event_is_recovered_by_reconciliation(self) -> None:
        manager = self._manager()
        self._current_pdf(manager)
        self.bib.write_text("@book{second,title={Second}}", encoding="utf-8")
        self.window.dependencies.reconcile()
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        self.assertEqual(self.window.pdf_state.record_for(manager.root_file).freshness, PdfFreshness.DIRTY)

    def test_new_include_adopts_already_open_child_and_flushes_before_compile(self) -> None:
        parent = self.root / "later.tex"
        parent.write_text("\\documentclass{article}\n\\begin{document}Root\\end{document}")
        self.window.open_file(self.child)
        child_tab = self.window.current_tab()
        self.window.open_file(parent)
        parent_tab = self.window.current_tab()
        parent_tab.editor.setPlainText("\\documentclass{article}\n\\begin{document}Root \\input{child}\\end{document}")
        self.window.dependencies.refresh_memberships()
        manager = self._manager(parent_tab)
        before = self.window.pdf_state.record_for(parent).source_revision
        child_tab.editor.setPlainText("unsaved child content")
        self.assertEqual(self.child.read_text(), "one")
        self.assertEqual(self.window.pdf_state.record_for(parent).source_revision, before + 1)
        self.assertTrue(self.window.documents.flush_root_documents(manager.root_file))
        self.assertEqual(self.child.read_text(), "unsaved child content")
        child_tab.editor.setPlainText("another local edit")
        self.child.write_text("external content")
        self.window.reload_external_change(str(self.child))
        self.assertTrue(child_tab.external_conflict)
        self.assertFalse(self.window.documents.flush_root_documents(manager.root_file))
        self.assertEqual(self.child.read_text(), "external content")

    def test_queued_started_signal_preserves_request_revision_after_new_edit(self) -> None:
        manager = self._manager()
        self._current_pdf(manager)
        finished = threading.Event()
        original_emit = self.window.compile._emit_finished

        def emit(owner, result):
            original_emit(owner, result)
            finished.set()

        def run(build_id, purpose, **kwargs):
            return CompileResult(
                root_file=manager.root_file, output_dir=manager.output_dir,
                pdf_file=manager.pdf_file, log_file=manager.log_file, command=[],
                returncode=0, stdout="", stderr="", duration_seconds=0.1,
                outcome=CompileOutcome.SUCCESS, build_id=build_id, purpose=purpose,
            )

        with patch.object(self.window.compile, "_emit_finished", side_effect=emit), \
             patch.object(manager, "_run_compile", side_effect=run):
            manager.compile_async()
            # Deliberately do not process Qt's queued started/finished signals.
            self.assertTrue(finished.wait(2))
            self.tab.editor.insertPlainText("new edit ")
            self.assertTrue(wait_until(lambda: not self.window.compile_build_owners))
        record = self.window.pdf_state.record_for(manager.root_file)
        self.assertEqual(record.last_successful_revision, 0)
        self.assertEqual(record.source_revision, 1)
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)

    def test_observation_is_off_thread_and_closed_root_drops_late_results(self) -> None:
        manager = self._manager()
        self._current_pdf(manager)
        entered = threading.Event()
        release = threading.Event()
        worker_ids = []

        def delayed(path, scope):
            worker_ids.append(threading.get_ident())
            if path == self.child:
                entered.set()
                release.wait(3)
            return observe_input(path, scope)

        try:
            with patch("app.gui.dependency_controller.observe_input", side_effect=delayed):
                self.child.write_text("changed")
                self.window.reload_external_change(str(self.child))
                self.assertTrue(wait_until(entered.is_set))
                heartbeat = []
                QTimer.singleShot(0, lambda: heartbeat.append(True))
                self.assertTrue(wait_until(lambda: bool(heartbeat)))
                self.window.compile_authorized_roots.add(manager.root_file)
                self.window.close_tab(0)
                self.assertNotIn(manager.root_file, self.window.compile_authorized_roots)
                self.assertNotIn(self.child, self.window.file_watcher._files)
                self.window.open_file(self.source)
                reopened_revision = self.window.pdf_state.record_for(manager.root_file).source_revision
                release.set()
                self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
                self.assertEqual(self.window.pdf_state.record_for(manager.root_file).source_revision, reopened_revision)
                self.assertEqual(self.window.pdf_state.record_for(manager.root_file).freshness, PdfFreshness.DIRTY)
                self.assertTrue(all(identifier != threading.get_ident() for identifier in worker_ids))
        finally:
            release.set()
