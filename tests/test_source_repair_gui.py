from copy import deepcopy
from dataclasses import replace
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from app.core.blocks.model import Provenance
from app.core.blocks.property_draft import PropertyDraft, table_projection
from app.core.blocks.registry import BlockRegistry, CreateBlockInput
from app.core.blocks.source_registry import SourceRecord
from app.core.blocks.source_repair import capture_source, verify_capture
from app.core.blocks.table_import import read_csv_text
from app.core.blocks.table_model import Cell
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.source_repair_session import SourceRepairSnapshot
from app.gui.blocks.source_repair_dialog import _read_in_background, SourceTableMappingDialog


class SourceRepairSessionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.original = b"Key,Value\nA,10\nB,20\n"
        (self.root / "base.csv").write_bytes(self.original)
        (self.root / "data.csv").write_bytes(b"Key,Value\nA,11\nB,21\n")
        self.record = SourceRecord("source", "csv", "data.csv", hashlib.sha256(self.original).hexdigest())
        registry = BlockRegistry()
        self.blocks = []
        for index in range(2):
            content = read_csv_text(self.original.decode()).to_content_dict()
            content["header"]["opaque"] = {"keep": index}
            content["rows"][1]["cells"]["col_1"]["opaque"] = "retain me"
            self.blocks.append(registry.create(CreateBlockInput(type="table", alias=f"Table {index}",
                content=content, provenance=Provenance("imported", "source"))))
        self.session = ProjectSession(registry=registry, sources=[self.record], project_dir=self.root)
        self.session.save_now()
        self.assertTrue(self.session.last_save_ok, self.session.save_error)
        self.session.pause_writes()
        self.addCleanup(self.dispose)
        self.base = capture_source(self.root, "base.csv", expected_sha=self.record.baseSha256)
        self.remote = capture_source(self.root, "data.csv")

    def dispose(self):
        self.session.shutdown()
        self.session.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def candidate(self, snapshot):
        candidates = deepcopy(snapshot.local_tables)
        for data in candidates.values():
            data.rows[2].cells["col_2"] = Cell("number", 21)
        return candidates

    def test_all_targets_and_baseline_apply_as_one_undo_with_opaque_fields(self):
        before = deepcopy([b.content for b in self.blocks])
        snapshot = SourceRepairSnapshot.capture(self.session, "source")
        self.assertTrue(verify_capture(self.remote))
        snapshot.apply_verified(self.session, self.candidate(snapshot), self.base, self.remote)
        self.assertEqual(self.session.undo_stack.count(), 1)
        self.assertEqual(self.session.sources[0].baseSha256, self.remote.sha256)
        for block in self.blocks:
            self.assertEqual(block.content["rows"][1]["cells"]["col_1"]["opaque"], "retain me")
            self.assertEqual(block.content["rows"][2]["cells"]["col_2"]["value"], 21)
        self.session.undo_stack.undo()
        self.assertEqual([b.content for b in self.blocks], before)
        self.assertEqual(self.session.sources, [self.record])
        self.session.undo_stack.redo()
        self.assertEqual(self.session.sources[0].baseSha256, self.remote.sha256)
        self.assertEqual((self.root / "data.csv").read_bytes(), self.remote.payload)
        self.assertEqual((self.root / "base.csv").read_bytes(), self.original)

    def test_unapplied_table_draft_is_included_and_restored_by_undo(self):
        block = self.blocks[0]
        initial = table_projection(block.content)
        values = deepcopy(initial)
        values["rows"][1]["cells"]["col_2"]["value"] = 12
        draft = PropertyDraft("table", block.id, "Local", deepcopy(block.to_dict()), initial, values)
        self.session.set_editor_draft(draft)
        snapshot = SourceRepairSnapshot.capture(self.session, "source")
        snapshot.apply_verified(self.session, self.candidate(snapshot), self.base, self.remote)
        self.assertNotIn(draft.key, self.session.editor_drafts)
        self.assertEqual(block.content["rows"][1]["cells"]["col_2"]["value"], 12)
        self.session.undo_stack.undo()
        restored = self.session.editor_drafts[draft.key]
        self.assertEqual(restored.values, draft.values)
        self.assertEqual(restored.base, block.to_dict())
        self.session.undo_stack.redo()
        self.assertNotIn(draft.key, self.session.editor_drafts)

    def test_missing_target_candidate_and_changed_source_refuse_without_mutation(self):
        snapshot = SourceRepairSnapshot.capture(self.session, "source")
        candidates = self.candidate(snapshot)
        before = deepcopy([b.to_dict() for b in self.blocks])
        with self.assertRaises(ValueError):
            snapshot.apply_verified(self.session, {next(iter(candidates)): next(iter(candidates.values()))}, self.base, self.remote)
        (self.root / "data.csv").write_bytes(b"newer external version")
        with self.assertRaises(ValueError):
            snapshot.apply_verified(self.session, candidates, self.base, self.remote)
        self.assertEqual([b.to_dict() for b in self.blocks], before)
        self.assertEqual(self.session.undo_stack.count(), 0)
        self.assertEqual(self.session.sources, [self.record])

    def test_target_revision_source_set_and_close_are_cas_guards(self):
        for mutation in ("target", "source", "close"):
            with self.subTest(mutation=mutation):
                snapshot = SourceRepairSnapshot.capture(self.session, "source")
                if mutation == "target":
                    self.blocks[0].revision += 1
                elif mutation == "source":
                    self.session.sources[0] = replace(self.record, relativePath="base.csv")
                else:
                    self.session._closed = True
                with self.assertRaises(ValueError):
                    snapshot.apply_verified(self.session, self.candidate(snapshot), self.base, self.remote)
                self.assertEqual(self.session.undo_stack.count(), 0)
                self.session.sources[:] = [self.record]

    def test_false_and_zero_are_different_target_versions(self):
        self.blocks[0].content["rows"][1]["cells"]["col_1"] = {"kind": "text", "value": 0}
        snapshot = SourceRepairSnapshot.capture(self.session, "source")
        self.blocks[0].content["rows"][1]["cells"]["col_1"]["value"] = False
        with self.assertRaises(ValueError):
            snapshot.validate(self.session)

    def test_changed_draft_after_capture_does_not_get_consumed(self):
        snapshot = SourceRepairSnapshot.capture(self.session, "source")
        block = self.blocks[0]
        initial = table_projection(block.content)
        values = deepcopy(initial)
        values["rows"][1]["cells"]["col_2"]["value"] = 99
        draft = PropertyDraft("table", block.id, "new input", deepcopy(block.to_dict()), initial, values)
        self.session.set_editor_draft(draft)
        with self.assertRaises(ValueError):
            snapshot.apply_verified(self.session, self.candidate(snapshot), self.base, self.remote)
        self.assertEqual(self.session.editor_drafts[draft.key], draft)
        self.assertEqual(self.session.undo_stack.count(), 0)

    def test_non_table_link_and_unknown_format_cannot_advance_shared_source(self):
        block = self.session.registry.create(CreateBlockInput(type="text", alias="Linked note",
            content={"format": "plain", "text": "keep"}, provenance=Provenance("imported", "source")))
        with self.assertRaises(ValueError):
            SourceRepairSnapshot.capture(self.session, "source")
        self.session.registry.remove(block.id)
        self.blocks[0].content["tableVersion"] = "999"
        with self.assertRaises(ValueError):
            SourceRepairSnapshot.capture(self.session, "source")
        self.assertEqual(self.session.sources, [self.record])

    def test_external_metadata_guard_is_read_only_and_refuses_changed_bytes(self):
        original = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.session._write_guard.check_current()
        self.assertEqual({p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}, original)
        path = self.root / ".icstex/sources.json"
        changed = path.read_bytes() + b"\n "
        path.write_bytes(changed)
        with self.assertRaises(OSError):
            self.session._write_guard.check_current()
        self.assertEqual(path.read_bytes(), changed)

    def test_background_cancel_and_shutdown_ignore_late_result(self):
        for action in ("cancel", "shutdown"):
            with self.subTest(action=action):
                release = threading.Event()
                done = threading.Event()
                def work(cancelled):
                    release.wait(1)
                    done.set()
                    return "late result"
                def stop():
                    if action == "shutdown":
                        self.session.shutdown()
                    else:
                        self.app.activeModalWidget().reject()
                QTimer.singleShot(10, stop)
                result = _read_in_background(None, self.session, work)
                self.assertIsNone(result)
                release.set()
                self.assertTrue(done.wait(1))
                self.app.processEvents()
                self.assertEqual(self.session.undo_stack.count(), 0)

    def test_changed_import_options_discard_late_parse_result(self):
        snapshot = SourceRepairSnapshot.capture(self.session, "source")
        dialog = SourceTableMappingDialog(self.session, snapshot, self.blocks[0].id, self.base, self.remote)
        parsed = (deepcopy(snapshot.local_tables[self.blocks[0].id]),) * 2
        def changed(*_args):
            dialog.encoding.setCurrentIndex(1)
            return parsed
        try:
            with patch("app.gui.blocks.source_repair_dialog._read_in_background", side_effect=changed):
                dialog._load()
            self.assertIsNone(dialog.parsed)
            self.assertFalse(dialog.preview_button.isEnabled())
        finally:
            dialog.deleteLater()

    def test_whole_table_choice_is_explicit_and_has_nonpositional_new_ids(self):
        from app.gui.blocks.merge_dialog import MergeDialog
        snapshot = SourceRepairSnapshot.capture(self.session, "source")
        dialog = SourceTableMappingDialog(self.session, snapshot, self.blocks[0].id, self.base, self.remote)
        old = deepcopy(self.blocks[0].to_dict())
        dialog.parsed = (read_csv_text(self.original.decode()), read_csv_text("New\nretained\n"))
        dialog.mode.setCurrentIndex(1)
        observed = []
        def choose():
            modal = self.app.activeModalWidget()
            if not isinstance(modal, MergeDialog):
                observed.append("not merge")
                return
            modal.table_remote_button.setChecked(True)
            modal.preview_button.click()
            observed.append(modal._candidate is not None)
            modal.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
        try:
            QTimer.singleShot(10, choose)
            dialog._preview()
            self.assertEqual(observed, [True])
            self.assertIsNotNone(dialog.candidate)
            self.assertEqual(dialog.candidate.rows[1].cells[dialog.candidate.columns[0].id].value, "retained")
            self.assertTrue(set(dialog.candidate.column_ids()).isdisjoint(snapshot.local_tables[self.blocks[0].id].column_ids()))
            self.assertEqual(self.blocks[0].to_dict(), old)
            self.assertEqual(self.session.undo_stack.count(), 0)
        finally:
            dialog.deleteLater()

    def test_mapping_rows_fit_real_combo_controls_and_use_available_width(self):
        snapshot = SourceRepairSnapshot.capture(self.session, "source")
        dialog = SourceTableMappingDialog(self.session, snapshot, self.blocks[0].id, self.base, self.remote)
        try:
            font = dialog.font()
            font.setPointSize(18)
            dialog.setFont(font)
            dialog.show()
            dialog._load()
            self.app.processEvents()
            for row in range(dialog.mapping.rowCount()):
                for column in (1, 2):
                    combo = dialog.mapping.cellWidget(row, column)
                    self.assertGreaterEqual(dialog.mapping.rowHeight(row), combo.sizeHint().height())
            self.assertGreaterEqual(sum(dialog.mapping.columnWidth(i) for i in range(3)),
                                    dialog.mapping.viewport().width() - 3)
        finally:
            dialog.close()
            dialog.deleteLater()

    def test_cancelled_parser_must_finish_before_another_worker_starts(self):
        release = threading.Event()
        started = []
        def work(cancelled):
            started.append(threading.current_thread())
            release.wait(2)
            return "late"
        try:
            QTimer.singleShot(10, lambda: self.app.activeModalWidget().reject())
            self.assertIsNone(_read_in_background(None, self.session, work))
            # A cancellation cannot stop an in-progress third-party parse; a
            # second click must not create an unbounded set of such workers.
            QTimer.singleShot(10, lambda: self.app.activeModalWidget().reject()
                              if self.app.activeModalWidget() else None)
            with self.assertRaisesRegex(ValueError, "尚未结束"):
                _read_in_background(None, self.session, work)
            self.assertEqual(len(started), 1)
        finally:
            release.set()
            for thread in started:
                thread.join(1)
