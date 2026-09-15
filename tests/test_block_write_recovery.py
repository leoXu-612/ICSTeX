import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.blocks.assembly import build_latex_files
from app.core.blocks.model import content_for_text
from app.core.blocks.project_repository import load_project, project_payloads
from app.core.blocks.project_write import BlockWriteGuard, PENDING_PATH
from app.core.blocks.write_recovery import inspect_write_journal, journal_candidate, recover_write_journal
from app.core.project_checkpoint import DraftInput
from app.core.project_recovery import read_recovery_copy
from tests.v1_fixtures import create_project


def interrupted_write(project, *, external=False, terminate=False):
    loaded = load_project(project)
    model = {key: loaded[key] for key in ("registry", "layout", "sources", "document_theme")}
    before_metadata = project_payloads(project, **model)
    arguments = {key: model[key] for key in ("registry", "layout", "document_theme")}
    before_generated = {p: s.encode() for p, s in build_latex_files(project, **arguments).items()}
    guard = BlockWriteGuard(project, before_metadata, before_generated)
    block = model["registry"].blocks()[0]
    model["registry"].update(block.id, {"content": content_for_text("Recovered interrupted Block write.")})
    after = {**project_payloads(project, **model),
             **{p: s.encode() for p, s in build_latex_files(project, **arguments).items()}}
    if terminate:
        original = guard._replace
        def replace(path, data, expected):
            original(path, data, expected)
            if path in after:
                os._exit(73)
        guard._replace = replace
        guard.write(after)
        raise AssertionError("The synthetic writer did not terminate")
    changed = {p: data for p, data in after.items() if data != guard.expected[p]}
    guard._journal(changed, guard.expected)
    path = next(iter(changed))
    guard._replace(path, changed[path], guard.expected[path])
    if external:
        generated = next(p for p in changed if p.parent.name == "blocks")
        generated.write_bytes(b"External manual winner.\r\n")
    return changed


class BlockWriteRecoveryTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-write-recovery-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        fixture = create_project(self.home, "block")
        self.project = fixture.root.parent
        self.saved = self.bytes()

    def bytes(self):
        return {p.relative_to(self.project).as_posix(): p.read_bytes()
                for p in self.project.rglob("*") if p.is_file()}

    def prepare(self, external=False):
        interrupted_write(self.project, external=external)
        return inspect_write_journal(self.project)

    def choices(self, review, side):
        return {entry.path: side for entry in review.entries}

    def test_partial_write_states_and_before_after_copies_preserve_all_evidence(self):
        review = self.prepare(external=True)
        original = self.bytes()
        self.assertEqual({entry.state for entry in review.entries}, {"after", "external"})
        drafts = [DraftInput("unsaved", "source-text", "main.tex", b"Independent unsaved draft")]
        for side in ("before", "after"):
            result = recover_write_journal(review, self.choices(review, side), self.home / side, drafts=drafts)
            copy = read_recovery_copy(result.directory)
            self.assertEqual(dict(copy.drafts)["unsaved"], drafts[0].payload)
            self.assertFalse((result.project_dir / PENDING_PATH).exists())
            loaded = load_project(result.project_dir)
            expected = "Synthetic analysis." if side == "before" else "Recovered interrupted Block write."
            self.assertEqual(loaded["registry"].blocks()[0].content["text"], expected)
            report = json.loads((result.directory / "recovery-evidence/decision.json").read_bytes())
            self.assertTrue(all(row["choice"] == side for row in report["entries"]))
            self.assertNotIn(str(self.project), json.dumps(report))
            for index, entry in enumerate(review.entries):
                if entry.current is not None:
                    self.assertEqual((result.directory / f"recovery-evidence/current-{index}.bin").read_bytes(), entry.current)
            self.assertEqual(self.bytes(), original)
        self.assertEqual({p: (self.home / "before/project" / p).read_bytes() for p in self.saved}, self.saved)

    def test_every_choice_required_and_inconsistent_models_are_not_published(self):
        review = self.prepare()
        with self.assertRaises(ValueError):
            journal_candidate(review, {})
        with self.assertRaisesRegex(ValueError, "不一致"):
            recover_write_journal(review, self.choices(review, "current"), self.home / "bad")
        self.assertFalse((self.home / "bad").exists())
        with self.assertRaises(ValueError):
            recover_write_journal(review, self.choices(review, "after"), self.project / "nested")
        self.assertFalse((self.project / "nested").exists())

    def test_corrupt_missing_unknown_linked_or_extra_journal_is_refused(self):
        review = self.prepare()
        journal = self.project / PENDING_PATH
        original = self.bytes()
        target = journal / "after-0.bin"
        payload = target.read_bytes()
        target.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            inspect_write_journal(self.project)
        target.unlink()
        with self.assertRaises(OSError):
            inspect_write_journal(self.project)
        target.symlink_to(self.project / "main.tex")
        with self.assertRaises((ValueError, OSError)):
            inspect_write_journal(self.project)
        target.unlink()
        target.write_bytes(payload)
        (journal / "unexpected.tmp").write_bytes(b"incomplete")
        with self.assertRaises(ValueError):
            inspect_write_journal(self.project)
        (journal / "unexpected.tmp").unlink()
        manifest = json.loads((journal / "manifest.json").read_bytes())
        for invalid in (2, True):
            manifest["version"] = invalid
            (journal / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                inspect_write_journal(self.project)
        self.assertEqual({p: self.bytes()[p] for p in self.saved}, {p: original[p] for p in self.saved})

    def test_manifest_target_traversal_duplicate_and_nonowned_path_refuse(self):
        self.prepare()
        target = self.project / PENDING_PATH / "manifest.json"
        data = json.loads(target.read_bytes())
        for path in ("../outside.tex", ".git/config", "figures/private.tex"):
            changed = json.loads(json.dumps(data))
            changed["entries"][0]["path"] = path
            target.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                inspect_write_journal(self.project)
        data["entries"][1]["path"] = data["entries"][0]["path"]
        target.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            inspect_write_journal(self.project)

    def test_source_change_after_review_and_before_publication_refuses(self):
        review = self.prepare()
        path = self.project / "main.tex"
        old = path.read_bytes()
        path.write_bytes(old + b"external change")
        with self.assertRaises(OSError):
            recover_write_journal(review, self.choices(review, "after"), self.home / "early")
        path.write_bytes(old)
        review = inspect_write_journal(self.project)
        from app.core import project_checkpoint
        original = project_checkpoint._write_restored
        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[1] == "README.txt":
                path.write_bytes(b"late external winner")
            return result
        with patch.object(project_checkpoint, "_write_restored", side_effect=mutate), self.assertRaises(OSError):
            recover_write_journal(review, self.choices(review, "after"), self.home / "late")
        self.assertFalse((self.home / "early").exists())
        self.assertFalse((self.home / "late").exists())
        self.assertEqual(path.read_bytes(), b"late external winner")

    def test_cancellation_disk_failure_and_existing_target_preserve_original(self):
        review = self.prepare()
        original = self.bytes()
        with self.assertRaises(OSError):
            recover_write_journal(review, self.choices(review, "after"), self.home / "cancel", cancelled=lambda: True)
        with patch("app.core.project_checkpoint._write_restored", side_effect=OSError("synthetic disk full")):
            with self.assertRaises(OSError):
                recover_write_journal(review, self.choices(review, "after"), self.home / "full")
        destination = self.home / "occupied"
        destination.mkdir()
        (destination / "keep").write_bytes(b"existing")
        with self.assertRaises(OSError):
            recover_write_journal(review, self.choices(review, "after"), destination)
        self.assertFalse((self.home / "cancel").exists())
        self.assertFalse((self.home / "full").exists())
        self.assertEqual((destination / "keep").read_bytes(), b"existing")
        self.assertEqual(self.bytes(), original)

    def test_real_writer_process_exit_preserves_journal_and_recovers_after(self):
        code = "from pathlib import Path; from tests.test_block_write_recovery import interrupted_write; import sys; interrupted_write(Path(sys.argv[1]), terminate=True)"
        result = subprocess.run([sys.executable, "-c", code, str(self.project)],
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 73, result.stderr.decode())
        review = inspect_write_journal(self.project)
        self.assertEqual({entry.state for entry in review.entries}, {"before", "after"})
        recovered = recover_write_journal(review, self.choices(review, "after"), self.home / "process-recovery")
        self.assertEqual(load_project(recovered.project_dir)["registry"].blocks()[0].content["text"],
                         "Recovered interrupted Block write.")
        self.assertTrue((self.project / PENDING_PATH).is_dir())
