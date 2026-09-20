from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import sys
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

    def test_source_edit_reuses_the_open_tabs_path_identity(self) -> None:
        record = self.window.pdf_state.record_for(self.source)
        before = record.source_revision
        with patch("app.gui.main_window.normalize_path",
                   side_effect=AssertionError("Do not resolve an open tab again during typing")):
            self.window._mark_source_edited(self.tab)
        self.assertEqual(record.source_revision, before + 1)
        self.assertEqual(record.freshness, PdfFreshness.DIRTY)

    def test_typing_burst_defers_background_scans_until_pause(self) -> None:
        from PySide6.QtTest import QTest
        self.assertTrue(wait_until(lambda: not self.window.word_counts.is_busy))
        with patch.object(self.window.dependencies, "_start_membership") as membership, \
             patch.object(self.window.word_counts, "_launch") as count:
            for _ in range(3):
                self.tab.editor.insertPlainText("x")
                QTest.qWait(260)
                membership.assert_not_called()
                count.assert_not_called()
            self.assertTrue(wait_until(lambda: membership.called and count.called, timeout=1))
            self.assertEqual(membership.call_count, 1)
            self.assertEqual(count.call_count, 1)

    def test_save_boundary_keeps_the_tabs_parent_path_canonical(self) -> None:
        folder = self.root / "nested"
        folder.mkdir()
        alias = folder / ".." / "saved.tex"
        original = self.source.read_bytes()
        self.assertTrue(self.window.documents.save_tab(self.tab, alias))
        self.assertEqual(self.tab.path, self.root / "saved.tex")
        self.assertEqual(self.window.local_save_contents[self.tab.path], self.tab.editor.toPlainText())
        self.assertEqual(self.tab.path.read_text(encoding="utf-8"), self.tab.editor.toPlainText())
        self.assertEqual(self.source.read_bytes(), original)

    def test_replaced_child_symlink_still_invalidates_its_open_buffer_owners(self) -> None:
        first = self._manager()
        second_path = self.root / "second.tex"
        second_path.write_text("\\documentclass{article}\n\\input{child}", encoding="utf-8")
        self.window.open_file(second_path)
        second = self._manager(self.window.current_tab())
        self.window.open_file(self.child)
        child_tab = self.window.current_tab()
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        owners = {first.root_file, second.root_file}
        self.assertEqual(len(owners), 2)
        self.assertTrue(owners.issubset(self.window.dependencies.roots_for(self.child)))
        before = {root: self.window.pdf_state.record_for(root).source_revision for root in owners}
        with TemporaryDirectory() as outside:
            replacement = Path(outside) / "unrelated.tex"
            replacement.write_bytes(b"Unrelated synthetic original")
            self.child.unlink()
            self.child.symlink_to(replacement)
            with patch.object(self.window.dependencies, "roots_for",
                              wraps=self.window.dependencies.roots_for) as lookup:
                self.window._mark_source_edited(child_tab)
            lookup.assert_called_once_with(self.child)
            for root in owners:
                record = self.window.pdf_state.record_for(root)
                self.assertEqual(record.source_revision, before[root] + 1)
                self.assertEqual(record.freshness, PdfFreshness.DIRTY)
            self.assertEqual(child_tab.path, self.child)
            self.assertEqual(child_tab.editor.toPlainText(), "one")
            self.assertEqual(replacement.read_bytes(), b"Unrelated synthetic original")
        self.assertFalse(any(".latex_build" in path.parts for path in self.window.file_watcher._files))

    def test_membership_scan_never_runs_on_gui_thread(self) -> None:
        from app.gui import dependency_controller
        original = dependency_controller.static_dependencies
        threads = []

        def observed(*args, **kwargs):
            threads.append(threading.get_ident())
            return original(*args, **kwargs)

        with patch.object(dependency_controller, "static_dependencies", side_effect=observed):
            self.tab.editor.insertPlainText("% new revision\n")
            self.window.dependencies.refresh_memberships()
            self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        self.assertTrue(threads)
        self.assertNotIn(threading.get_ident(), threads)

    def test_ready_automatic_preview_does_not_force_another_membership_job(self):
        manager = self._manager()
        self.window.dependencies.refresh_memberships(force=True)
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        self.assertTrue(self.window.dependencies.memberships_current)
        self.window.auto_compile_action.setChecked(True)
        self.window.compile_authorized_roots.add(manager.root_file)
        with patch.object(self.window.dependencies, "refresh_memberships") as refresh, \
                patch.object(manager, "compile_async") as compiled:
            self.window.compile.compile_for_root(
                manager.root_file, BuildPurpose.PREVIEW, reason="automatic edit", immediate=True)
            compiled.assert_called_once_with(BuildPurpose.PREVIEW)
            refresh.assert_not_called()

    def test_pending_automatic_compile_defers_background_count_but_not_explicit_count(self):
        manager = self._manager()
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy
                                  and not self.window.word_counts.is_busy))
        self.window.auto_compile_action.setChecked(True)
        self.window.compile_authorized_roots.add(manager.root_file)
        self.tab.editor.insertPlainText("New text ")
        with patch.object(self.window.word_counts, "_launch") as launch:
            self.window.update_word_count()
            launch.assert_not_called()
            self.assertTrue(self.window.word_counts._timer.isActive())
            self.window.update_word_count(force=True)
            launch.assert_called_once()

    def test_own_save_does_not_replace_immediate_preview_with_external_debounce(self):
        manager = self._manager()
        self.window.dependencies.refresh_memberships(force=True)
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        self.window.auto_compile_action.setChecked(True)
        self.window.compile_authorized_roots.add(manager.root_file)
        generation = self.window.dependencies.generation_for(manager.root_file)
        self.tab.editor.insertPlainText("New text ")
        with patch.object(manager, "compile_async") as immediate, \
                patch.object(manager, "schedule_compile") as scheduled:
            self.assertTrue(self.window.flush_pending_save(self.tab))
            self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
            immediate.assert_called_once_with(BuildPurpose.PREVIEW)
            scheduled.assert_not_called()
        self.assertEqual(self.window.dependencies.generation_for(manager.root_file), generation)

    def test_scheduled_compile_keeps_count_deferred_until_cancelled(self):
        manager = self._manager()
        self.assertTrue(wait_until(lambda: not self.window.word_counts.is_busy))
        self.window.auto_compile_action.setChecked(True)
        self.window.compile_authorized_roots.add(manager.root_file)
        manager.debounce_ms = 60_000
        manager.schedule_compile("external edit", BuildPurpose.PREVIEW)
        self.addCleanup(manager.cancel_pending)
        self.window.word_counts._cache.clear()
        self.assertFalse(manager.is_busy)
        with patch.object(self.window.word_counts, "_launch") as launch:
            self.window.update_word_count()
            launch.assert_not_called()
            manager.cancel_pending()
            self.window.update_word_count(force=True)
            launch.assert_called_once()

    def test_typing_uses_cached_root_without_disk_resolution(self) -> None:
        with patch("app.gui.main_window.resolve_root_tex", wraps=__import__(
                "app.core.paths", fromlist=["resolve_root_tex"]).resolve_root_tex) as resolve:
            self.tab.editor.insertPlainText("% typing\n")
            self.assertEqual(resolve.call_count, 0)

    def _held_membership(self):
        from app.gui import dependency_controller
        entered, release = threading.Event(), threading.Event()
        calls = []
        original = dependency_controller.static_dependencies

        def delayed(root, scope, buffers, **kwargs):
            calls.append((root, buffers.get(root)))
            if not entered.is_set():
                entered.set()
                release.wait(5)
            return original(root, scope, buffers, **kwargs)

        self.addCleanup(release.set)
        return patch.object(dependency_controller, "static_dependencies", side_effect=delayed), entered, release, calls

    def test_membership_worker_keeps_one_latest_snapshot_and_retains_old_watches(self):
        held, entered, release, calls = self._held_membership()
        source = self.source.read_text()
        with held:
            self.tab.editor.insertPlainText("% first snapshot\n")
            self.window.dependencies.refresh_memberships()
            self.assertTrue(wait_until(entered.is_set))
            first = self.window.dependencies._membership_active
            for index in range(10):
                (self.root / f"new-{index}.tex").write_text(str(index))
                self.tab.editor.setPlainText(source + f"\n\\input{{new-{index}.tex}}")
                self.window.dependencies.refresh_memberships()
                self.assertIs(self.window.dependencies._membership_active, first)
            self.assertTrue(first.cancelled.is_set())
            self.assertIn(self.child, self.window.file_watcher._files)
            self.assertNotIn("new-9", dict(first.inputs.buffers)[self.source])
            latest = self.window.dependencies._membership_pending
            self.assertIn("new-9", dict(latest.inputs.buffers)[self.source])
            release.set()
            self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        self.assertEqual(len(calls), 2)
        self.assertIn(self.root / "new-9.tex", self.window.dependencies.paths_for(self.source))
        self.assertNotIn(self.root / "new-0.tex", self.window.dependencies.paths_for(self.source))

    def test_manual_compile_waits_for_new_dependency_then_flushes_latest_child(self):
        manager = self._manager()
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        late = self.root / "late.tex"
        late.write_text("saved child")
        self.window.open_file(late)
        late_tab = self.window.current_tab()
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        self.window.editor_tabs.setCurrentIndex(self.window._index_for_tab_id(id(self.tab.editor)))
        self.window.toolchain = LaTeXToolchain(None, sys.executable)
        held, entered, release, _ = self._held_membership()
        with held, patch.object(manager, "compile_async") as compiled:
            self.tab.editor.insertPlainText("\\input{late.tex}\n")
            self.window.dependencies.refresh_memberships()
            self.assertTrue(wait_until(entered.is_set))
            late_tab.editor.setPlainText("latest unsaved child")
            self.window.compile_current(immediate=True, purpose=BuildPurpose.FINAL)
            compiled.assert_not_called()
            self.assertEqual(late.read_text(), "saved child")
            self.assertEqual(len(self.window.compile._deferred_dependencies), 1)
            release.set()
            self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
            compiled.assert_called_once_with(BuildPurpose.FINAL)
        self.assertEqual(late.read_text(), "latest unsaved child")
        self.assertFalse(self.window.compile._deferred_dependencies)

    def test_stop_cancels_compile_waiting_for_graph_without_late_launch(self):
        manager = self._manager()
        self.window.toolchain = LaTeXToolchain(None, sys.executable)
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        held, entered, release, _ = self._held_membership()
        with held, patch.object(manager, "compile_async") as compiled:
            self.tab.editor.insertPlainText("% waiting\n")
            self.window.dependencies.refresh_memberships()
            self.assertTrue(wait_until(entered.is_set))
            self.window.compile_current(immediate=True)
            self.assertTrue(self.window.compile._deferred_dependencies)
            self.assertTrue(self.window.stop_compile_action.isEnabled())
            self.window.stop_compile_action.trigger()
            self.assertFalse(self.window.compile._deferred_dependencies)
            self.assertFalse(self.window.stop_compile_action.isEnabled())
            release.set()
            self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
            compiled.assert_not_called()

    def test_compile_rechecks_disk_root_before_using_cached_membership_for_flush(self):
        manager = self._manager()
        late = self.root / "late.tex"
        late.write_text("saved child")
        self.window.open_file(late)
        late_tab = self.window.current_tab()
        late_tab.editor.setPlainText("latest child draft")
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        self.window.editor_tabs.setCurrentIndex(self.window._index_for_tab_id(id(self.tab.editor)))
        # The fixture intentionally suppresses watcher notifications. A cached
        # graph is not independent proof that a new include is absent.
        self.source.write_text(self.source.read_text() + "\n\\input{late.tex}")
        self.window.toolchain = LaTeXToolchain(None, sys.executable)
        with patch.object(manager, "compile_async") as compiled:
            self.window.compile_current(immediate=True)
            self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
            self.assertEqual(late.read_text(), "latest child draft")
            compiled.assert_called_once_with(BuildPurpose.FINAL)
        self.assertIn("\\input{late.tex}", self.tab.editor.toPlainText())

    def test_failed_membership_retains_watches_and_ends_pending_compile(self):
        manager = self._manager()
        self.window.toolchain = LaTeXToolchain(None, sys.executable)
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        watched = set(self.window.file_watcher._files)
        with patch("app.gui.dependency_controller.calculate_memberships", side_effect=OSError("synthetic read failure")), \
             patch.object(manager, "compile_async") as compiled:
            self.window.compile_current(immediate=True)
            self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
            compiled.assert_not_called()
        self.assertFalse(self.window.compile._deferred_dependencies)
        self.assertEqual(self.window.file_watcher._files, watched)
        self.assertFalse(self.window.dependencies.memberships_current)

    def test_closed_window_discards_membership_worker_result(self):
        from app.gui import dependency_controller
        done = threading.Event()
        original = dependency_controller._membership_work

        def tracked(*args):
            try:
                original(*args)
            finally:
                done.set()

        held, entered, release, _ = self._held_membership()
        with held, patch.object(dependency_controller, "_membership_work", side_effect=tracked):
            self.tab.editor.insertPlainText("% close during calculation\n")
            self.window.dependencies.refresh_memberships()
            self.assertTrue(wait_until(entered.is_set))
            controller = self.window.dependencies
            with patch.object(controller, "_apply_memberships", wraps=controller._apply_memberships) as apply:
                self.tab.modified = self.tab.dirty = False
                self.assertTrue(self.window.close())
                release.set()
                self.assertTrue(done.wait(2))
                self.app.processEvents()
                apply.assert_not_called()
            self.assertTrue(controller._closed.is_set())

    def test_multiple_external_reloads_do_not_launch_overlapping_membership_jobs(self):
        from app.gui import dependency_controller
        self.window.open_file(self.child)
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
        self.source.write_text(self.source.read_text() + "\n% external root")
        self.child.write_text("external child")
        entered, release = threading.Event(), threading.Event()
        original = dependency_controller.calculate_memberships
        calls = []
        controller = self.window.dependencies
        start = controller._start_membership
        started = []

        def calculate(*args, **kwargs):
            calls.append(True)
            if len(calls) > 1:
                entered.set()
                release.wait(3)
            return original(*args, **kwargs)

        def launch(job):
            started.append(job)
            return start(job)

        with patch.object(dependency_controller, "calculate_memberships", side_effect=calculate), \
             patch.object(controller, "_start_membership", side_effect=launch):
            try:
                controller.refresh_memberships(force=True)
                self.assertTrue(wait_until(entered.is_set))
                # The first reply reloads two saved editors. The second job
                # is still held, so the third snapshot must only be pending.
                self.assertEqual(len(started), 2)
                self.assertIsNotNone(controller._membership_pending)
            finally:
                release.set()
                self.assertTrue(wait_until(lambda: not controller.is_busy))

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
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
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
        self.assertTrue(wait_until(lambda: not self.window.dependencies.is_busy))
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
        # Membership publication is intentionally asynchronous. The low-level
        # save API refuses stale membership; the compile controller resumes
        # its existing request once the current graph is available.
        self.assertFalse(self.window.documents.flush_root_documents(manager.root_file))
        self.assertTrue(wait_until(lambda: self.window.dependencies.memberships_current))
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
                self.assertTrue(wait_until(lambda: not self.window.file_watcher.has_pending_memberships))
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
