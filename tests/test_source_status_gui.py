"""Read-only source status, explicit refresh and late-worker ownership."""
from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
from unittest import TestCase
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QAbstractItemView

from app.core.blocks.model import Provenance, content_for_text
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.source_registry import SourceRecord, SourceStatus, hash_file
from app.core.blocks.table_model import Cell, ColumnSpec, TableData, TableRow
from app.gui.blocks.navigation_dock import BlockNavigationWidget
from app.gui.blocks.project_session import ProjectSession


class SourceStatusGuiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-source-check-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()
        source = self.project / "data.csv"
        source.write_bytes(b"value\n1\n")
        self.record = SourceRecord("src_one", "csv", "data.csv", hash_file(source))
        registry = BlockRegistry()
        data = TableData(columns=[ColumnSpec(id="value", name="Value")],
                         rows=[TableRow(id="row", cells={"value": Cell("text", "1")})], header_row_count=0)
        self.block = registry.create(CreateBlockInput(type="table", alias="Affected table",
                                                      content=data.to_content_dict()))
        self.block.provenance = Provenance(kind="imported", sourceId=self.record.sourceId)
        registry.create(CreateBlockInput(type="text", alias="Unrelated", content=content_for_text("Unrelated")))
        self.session = ProjectSession(registry=registry, sources=[self.record], project_dir=self.project)
        self.nav = None
        self.addCleanup(self.dispose)
        self.session.save_now()
        self.assertTrue(self.session.last_save_ok, self.session.save_error)

    def dispose(self):
        self.session.shutdown()
        if self.nav is not None:
            self.nav.close()
            self.nav.deleteLater()
        self.session.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def open_nav(self):
        self.nav = BlockNavigationWidget(self.session)
        return self.nav

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.001)
        self.assertTrue(predicate())

    def test_open_navigation_and_model_refresh_do_not_hash_sources(self):
        with patch("app.core.blocks.source_registry.hash_file", side_effect=AssertionError("unexpected I/O")):
            nav = self.open_nav()
            nav.search_edit.setText("table")
            self.session.model_changed.emit("synthetic refresh")
        self.assertIn("尚未检查", nav.sources_summary.text())
        self.assertEqual(nav.sources_table.editTriggers(), QAbstractItemView.EditTrigger.NoEditTriggers)

    def test_filter_typing_does_not_rebuild_source_or_layout_panels(self):
        nav = self.open_nav()
        with patch.object(nav, "_refresh_sources") as sources, patch.object(nav, "_refresh_layout") as layout:
            nav.search_edit.setText("Affected")
            nav.type_filter.setCurrentIndex(1)
        sources.assert_not_called()
        layout.assert_not_called()

    def test_refresh_is_background_read_only_and_lists_affected_blocks(self):
        nav = self.open_nav()
        baseline = deepcopy([block.to_dict() for block in self.session.registry.blocks()])
        original = {p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        (self.project / "data.csv").write_bytes(b"value\n2\n")
        original[self.project / "data.csv"] = b"value\n2\n"
        from app.gui.blocks import source_status
        check = source_status.check_sources
        worker_ids = []

        def observed(*args, **kwargs):
            worker_ids.append(threading.get_ident())
            return check(*args, **kwargs)

        with patch.object(source_status, "check_sources", observed), \
                patch.object(self.session, "request_save", side_effect=AssertionError("read-only")), \
                patch.object(self.session, "compile_final", side_effect=AssertionError("read-only")):
            nav.refresh_sources_button.click()
            self.wait_for(lambda: not nav.source_status.is_busy)
            nav.sources_table.selectRow(0)
            self.assertEqual(nav.source_status.results[0].state, "changed")
            self.assertIn("内容已变化", nav.sources_table.item(0, 1).text())
            self.assertEqual(nav.affected_blocks.count(), 1)
            self.assertEqual(nav.affected_blocks.item(0).data(Qt.ItemDataRole.UserRole), self.block.id)
            self.assertIn(self.record.baseSha256, nav.source_details.toPlainText())
            seen = []
            nav.block_selected.connect(seen.append)
            nav.affected_blocks.setCurrentRow(0)
            nav.locate_source_block_button.click()
            self.assertEqual(seen, [self.block.id])
        self.assertTrue(worker_ids)
        self.assertNotIn(threading.get_ident(), worker_ids)
        self.assertEqual(self.session.sources, [self.record])
        self.assertEqual([block.to_dict() for block in self.session.registry.blocks()], baseline)
        self.assertEqual({p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()}, original)
        self.assertEqual(self.session.undo_stack.count(), 0)

    def test_only_one_active_worker_and_latest_pending_request(self):
        from app.gui.blocks import source_status
        nav = self.open_nav()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        calls = []

        def blocked(project, records, **kwargs):
            calls.append(records)
            if len(calls) == 1:
                entered.set()
                release.wait(3)
            return tuple(SourceStatus("ok", record.relativePath, record.baseSha256) for record in records)

        with patch.object(source_status, "check_sources", blocked):
            nav.refresh_sources_button.click()
            self.wait_for(entered.is_set)
            for index in range(5):
                self.session.sources = [replace(self.record, relativePath=f"{index}.csv")]
                self.session.model_changed.emit("sources changed")
                nav.refresh_sources_button.click()
            self.assertEqual(len(calls), 1)
            release.set()
            self.wait_for(lambda: not nav.source_status.is_busy)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[-1][0].relativePath, "4.csv")
        self.assertEqual(nav.source_status.results[0].relativePath, "4.csv")

    def test_cancel_discards_even_a_worker_that_returns_success_late(self):
        self._late_result("cancel")

    def test_source_change_discards_late_results_without_a_new_scan(self):
        self._late_result("change")

    def test_project_close_discards_late_results(self):
        self._late_result("close")

    def _late_result(self, action):
        from app.gui.blocks import source_status
        nav = self.open_nav()
        entered, release, returned = threading.Event(), threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def blocked(project, records, **kwargs):
            entered.set()
            release.wait(3)
            returned.set()
            return (SourceStatus("ok", records[0].relativePath, records[0].baseSha256),)

        with patch.object(source_status, "check_sources", blocked):
            nav.refresh_sources_button.click()
            self.wait_for(entered.is_set)
            if action == "cancel":
                nav.cancel_sources_button.click()
            elif action == "change":
                self.session.sources = [replace(self.record, baseSha256="a" * 64)]
                self.session.model_changed.emit("sources changed")
            else:
                self.session.shutdown()
            release.set()
            self.wait_for(returned.is_set)
            self.wait_for(lambda: not nav.source_status.is_busy)
        self.assertEqual(nav.source_status.results, ())
        self.assertEqual(nav.source_status.checked_at, "")

    def test_completed_snapshot_is_invalidated_by_record_changes(self):
        nav = self.open_nav()
        nav.refresh_sources_button.click()
        self.wait_for(lambda: not nav.source_status.is_busy)
        self.assertTrue(nav.source_status.checked_at)
        self.session.sources = [replace(self.record, baseSha256="a" * 64)]
        self.session.model_changed.emit("sources changed")
        self.assertEqual(nav.source_status.results, ())
        self.assertEqual(nav.source_status.checked_at, "")
        self.assertIn("来源记录已变化", nav.sources_summary.text())

    def test_worker_failure_remains_unknown_and_refreshable(self):
        nav = self.open_nav()
        with patch("app.gui.blocks.source_status.check_sources", side_effect=OSError("synthetic failure")):
            nav.refresh_sources_button.click()
            self.wait_for(lambda: not nav.source_status.is_busy)
        self.assertEqual(nav.source_status.results, ())
        self.assertIn("未知", nav.sources_summary.text())
        self.assertTrue(nav.refresh_sources_button.isEnabled())

    def test_destroyed_widget_cancels_worker_without_a_late_ui_callback(self):
        from app.gui.blocks import source_status
        nav = self.open_nav()
        controller = nav.source_status
        entered, release, returned = threading.Event(), threading.Event(), threading.Event()
        self.addCleanup(release.set)
        cancelled = []

        def blocked(project, records, **kwargs):
            entered.set()
            release.wait(3)
            cancelled.append(kwargs["cancelled"]())
            returned.set()
            return (SourceStatus("ok", records[0].relativePath, records[0].baseSha256),)

        with patch.object(source_status, "check_sources", blocked):
            nav.refresh_sources_button.click()
            self.wait_for(entered.is_set)
            nav.deleteLater()
            self.nav = None
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self.assertTrue(controller._closed.is_set())
            release.set()
            self.wait_for(returned.is_set)
            self.app.processEvents()
        self.assertEqual(cancelled, [True])
        self.assertEqual(controller.results, ())

    def test_project_switch_discards_late_results(self):
        from app.gui.blocks import source_status
        nav = self.open_nav()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def blocked(project, records, **kwargs):
            entered.set()
            release.wait(3)
            return (SourceStatus("ok", records[0].relativePath, records[0].baseSha256),)

        with patch.object(source_status, "check_sources", blocked):
            nav.refresh_sources_button.click()
            self.wait_for(entered.is_set)
            self.session.project_dir = self.project / "different-project"
            release.set()
            self.wait_for(lambda: not nav.source_status.is_busy)
        self.assertEqual(nav.source_status.results, ())
        self.assertIn("未知", nav.sources_summary.text())
