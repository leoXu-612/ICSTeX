import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.project_checkpoint import DraftInput, create_checkpoint, restore_checkpoint
from app.core.project_recovery import (read_recovery_copy, check_recovery_identity,
    parse_block_draft, saved_block_model, selected_drafts)
from app.core.blocks.project_repository import load_project
from tests.v1_fixtures import create_project


def block_payload(project, *, unapplied=()):
    loaded = load_project(project)
    model = {"blocks": [b.to_dict() for b in loaded["registry"].blocks()],
             "layout": loaded["layout"].to_dict(), "sources": [],
             "document_theme": loaded["document_theme"].to_dict()}
    return {"format": "icstex-block-draft", "version": 1, "model": model, "unapplied": list(unapplied)}


class ProjectRecoveryTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-recovery-core-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.fixture = create_project(self.home, "multi")
        self.project = self.fixture.root.parent
        self.saved = self.fixture.draft_path.read_bytes()
        drafts = [DraftInput("source-a", "source-text", "chapters/analysis.tex", b"Recovered draft A"),
                  DraftInput("source-b", "source-text", "chapters/analysis.tex", b"Recovered draft B"),
                  DraftInput("untitled", "source-text", None, "未命名草稿".encode())]
        files = [p.relative_to(self.project).as_posix() for p in self.project.rglob("*") if p.is_file()]
        archive = self.home / "a.icstex-checkpoint"
        create_checkpoint(self.project, files, archive, drafts=drafts)
        self.restore = restore_checkpoint(archive, self.home / "recovered")

    def test_reads_all_saved_and_separate_drafts_without_writing(self):
        copy = read_recovery_copy(self.restore.directory)
        self.assertEqual(dict(copy.files)["chapters/analysis.tex"], self.saved)
        self.assertEqual(dict(copy.drafts)["source-b"], b"Recovered draft B")
        self.assertEqual(self.fixture.draft_path.read_bytes(), self.saved)
        self.assertEqual(selected_drafts(copy, ("source-a", "untitled"))[0].id, "source-a")
        for selection in ((), ("source-a", "source-b"), ("source-a", "source-a"), ("absent",)):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                selected_drafts(copy, selection)

    def test_changed_missing_linked_or_incomplete_copy_is_not_accepted(self):
        copy = read_recovery_copy(self.restore.directory)
        source = self.restore.project_dir / "chapters/analysis.tex"
        source.write_bytes(b"external winner")
        with self.assertRaises(OSError):
            check_recovery_identity(copy)
        with self.assertRaises(ValueError):
            read_recovery_copy(copy.directory)
        source.unlink()
        with self.assertRaises(OSError):
            read_recovery_copy(copy.directory)
        source.symlink_to(self.fixture.draft_path)
        with self.assertRaises((OSError, ValueError)):
            read_recovery_copy(copy.directory)
        incomplete = self.home / ".icstex-restore.incomplete-test"
        copy.directory.rename(incomplete)
        with self.assertRaises(ValueError):
            read_recovery_copy(incomplete)
        self.assertEqual(self.fixture.draft_path.read_bytes(), self.saved)

    def test_manifest_draft_change_and_cancellation_refuse(self):
        copy = read_recovery_copy(self.restore.directory)
        with self.assertRaises(OSError):
            read_recovery_copy(copy.directory, cancelled=lambda: True)
        (copy.directory / "drafts/source-a.txt").write_bytes(b"different valid text")
        with self.assertRaises(ValueError):
            read_recovery_copy(copy.directory, expected=copy)

    def test_change_between_passes_is_detected(self):
        from app.core import project_recovery
        original = project_recovery._read_file
        count = 0
        def read(root, path, stop):
            nonlocal count
            result = original(root, path, stop)
            if path == "project/chapters/analysis.tex":
                count += 1
                if count == 1:
                    (root / path).write_bytes(b"changed after first read")
            return result
        with patch.object(project_recovery, "_read_file", side_effect=read), self.assertRaises(OSError):
            read_recovery_copy(self.restore.directory)

    def test_actual_block_model_and_properties_roundtrip_unknown_fields_refuse(self):
        fixture = create_project(self.home, "block")
        payload = block_payload(fixture.root.parent)
        raw = payload["model"]["blocks"][0]
        payload["unapplied"] = [{"kind": "block", "target_id": raw["id"], "label": "别名草稿",
            "base": raw, "initial": {"alias": raw["alias"]}, "values": {"alias": "recovered alias"}}]
        model, drafts = parse_block_draft(json.dumps(payload).encode())
        self.assertEqual(model["registry"].blocks()[0].to_dict(), raw)
        self.assertEqual(drafts[("block", raw["id"])].values["alias"], "recovered alias")
        payload["version"] = 2
        with self.assertRaises(ValueError):
            parse_block_draft(json.dumps(payload).encode())
        payload["version"] = 1
        payload["model"]["document_theme"]["new_unknown_field"] = "do not discard"
        with self.assertRaises(ValueError):
            parse_block_draft(json.dumps(payload).encode())

    def test_saved_block_requires_complete_known_metadata(self):
        with self.assertRaises(ValueError):
            saved_block_model(read_recovery_copy(self.restore.directory))
        with self.assertRaises(ValueError):
            parse_block_draft(b'{"version":1,"version":2}')
