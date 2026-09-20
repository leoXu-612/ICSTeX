"""New-copy acceptance replaces the retired in-place runner's write expectations."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core import project_checkpoint, project_migration
from app.core.blocks.migration import MigrationError, MigrationRunner, RawLatexMigration, legacy_fixture
from app.core.blocks.project_repository import load_project
from app.core.blocks.project_write import PENDING_PATH
from app.core.project_checkpoint import DraftInput
from app.core.project_migration import inspect_project_migration, migrate_project_copy
from app.core.project_recovery import read_recovery_copy
from tests.v1_fixtures import create_project


class MigrationCopyTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-migration-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.project = self.home / "original"
        self.project.mkdir()

    def legacy(self):
        for path, payload in {
            ".icstex/blocks.json": json.dumps(legacy_fixture(), indent=1).replace("\n", "\r\n").encode(),
            "main.tex": b"% old manual source\r\n\\unknown{original}\r\n",
            "figures/a.png": b"synthetic-a",
            "figures/b.png": b"synthetic-b",
            "refs.bib": b"% original encoding \xe9\r\n",
        }.items():
            target = self.project / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        return self.files()

    def files(self, root=None):
        root = root or self.project
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}

    def test_legacy_verified_new_copy_loads_and_preserves_every_original_byte(self):
        before = self.legacy()
        review = inspect_project_migration(self.project)
        self.assertEqual(review.kind, "legacy-conversion")
        self.assertIn("main.tex", review.replaced)
        self.assertEqual(self.files(), before)
        draft = DraftInput("unsaved", "source-text", "main.tex", b"independent draft")
        result = migrate_project_copy(review, self.home / "converted", drafts=[draft])
        recovered = read_recovery_copy(result.directory)
        self.assertEqual(dict(recovered.files), dict(review.candidate))
        self.assertEqual(dict(recovered.drafts), {"unsaved": draft.payload})
        self.assertEqual(self.files(result.directory / "recovery-evidence/original"), before)
        loaded = load_project(result.project_dir)
        self.assertEqual(len(loaded["registry"].blocks()), 3)
        self.assertEqual(loaded["layout"].kind, "column")
        self.assertEqual(len(loaded["layout"].children[0].children), 2)
        snippet = next(b for b in loaded["registry"].blocks() if b.type == "rawLatex")
        self.assertEqual(snippet.content, {"latex": "E=mc^2", "trusted": False})
        self.assertEqual((result.project_dir / "refs.bib").read_bytes(), before["refs.bib"])
        report = (result.directory / "recovery-evidence/decision.json").read_bytes()
        self.assertNotIn(str(self.project).encode(), report)
        self.assertEqual(self.files(), before)
        # A second project-level operation is an exact current-format copy, not
        # another format migration with duplicated Blocks or normalized files.
        second_review = inspect_project_migration(result.project_dir)
        self.assertEqual(second_review.kind, "block-copy")
        second = migrate_project_copy(second_review, self.home / "second")
        self.assertEqual(self.files(second.project_dir), self.files(result.project_dir))

    def test_current_source_and_block_copies_keep_exact_selected_bytes(self):
        for kind in ("single", "block"):
            with self.subTest(kind=kind):
                fixture = create_project(self.home / kind, kind)
                project = fixture.root.parent
                review = inspect_project_migration(project)
                before = self.files(project)
                result = migrate_project_copy(review, self.home / (kind + "-copy"))
                self.assertEqual(self.files(project), before)
                self.assertEqual(dict(read_recovery_copy(result.directory).files), dict(review.original))
                self.assertEqual(review.original, review.candidate)

    def test_old_runner_refuses_without_even_backup_or_log_writes(self):
        before = self.legacy()
        for plans in ([], [RawLatexMigration()]):
            with self.assertRaises(MigrationError):
                MigrationRunner(self.project).run(plans)
            self.assertEqual(self.files(), before)

    def test_unknown_metadata_missing_assets_and_partial_selection_refuse(self):
        self.legacy()
        target = self.project / ".icstex/blocks.json"
        original = target.read_bytes()
        for payload in (b'{"format":"future","schemaVersion":"99"}',
                        b'{"format":"icstex-blocks","schemaVersion":"99","blocks":[]}'):
            target.write_bytes(payload)
            with self.assertRaises(ValueError):
                inspect_project_migration(self.project)
        target.write_bytes(original)
        with self.assertRaises(ValueError):
            inspect_project_migration(self.project, paths=["main.tex"])
        (self.project / "figures/a.png").unlink()
        with self.assertRaisesRegex(ValueError, "缺少"):
            inspect_project_migration(self.project)

    def test_read_race_and_same_mtime_external_edit_refuse_without_output(self):
        self.legacy()
        real_read = project_migration._read_file
        path = self.project / "main.tex"
        count = 0
        def mutate(*args, **kwargs):
            nonlocal count
            value = real_read(*args, **kwargs)
            if args[1] == "main.tex":
                count += 1
                if count == 1:
                    path.write_bytes(b"external changed while reading")
            return value
        with patch.object(project_migration, "_read_file", side_effect=mutate), self.assertRaises(OSError):
            inspect_project_migration(self.project)
        review = inspect_project_migration(self.project)
        old = path.stat()
        path.write_bytes(b"X" * old.st_size)
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
        with self.assertRaises(OSError):
            migrate_project_copy(review, self.home / "stale")
        self.assertFalse((self.home / "stale").exists())
        self.assertEqual(path.read_bytes(), b"X" * old.st_size)

    def test_late_change_cancellation_disk_failure_and_existing_target_preserve(self):
        before = self.legacy()
        review = inspect_project_migration(self.project)
        with self.assertRaises(OSError):
            migrate_project_copy(review, self.home / "cancel", cancelled=lambda: True)
        with patch.object(project_checkpoint, "_write_restored", side_effect=OSError("synthetic disk full")):
            with self.assertRaises(OSError):
                migrate_project_copy(review, self.home / "full")
        occupied = self.home / "occupied"
        occupied.mkdir()
        (occupied / "keep").write_bytes(b"keep")
        with self.assertRaises(OSError):
            migrate_project_copy(review, occupied)
        with self.assertRaises(ValueError):
            migrate_project_copy(review, self.project / "nested")
        self.assertEqual(self.files(), before)
        self.assertEqual((occupied / "keep").read_bytes(), b"keep")
        real_write = project_checkpoint._write_restored
        def late_change(*args, **kwargs):
            observation = real_write(*args, **kwargs)
            if args[1] == "README.txt":
                (self.project / "main.tex").write_bytes(b"late external winner")
            return observation
        with patch.object(project_checkpoint, "_write_restored", side_effect=late_change), self.assertRaises(OSError):
            migrate_project_copy(review, self.home / "late")
        self.assertEqual((self.project / "main.tex").read_bytes(), b"late external winner")
        for name in ("cancel", "full", "late"):
            self.assertFalse((self.home / name).exists())
        self.assertFalse(list(self.home.glob(".icstex-restore.incomplete-*")))

    def test_links_journal_and_new_format_marker_refuse(self):
        self.legacy()
        original = (self.project / "figures/a.png").read_bytes()
        (self.project / "figures/a.png").unlink()
        (self.project / "figures/a.png").symlink_to(self.project / "figures/b.png")
        with self.assertRaises((ValueError, OSError)):
            inspect_project_migration(self.project)
        (self.project / "figures/a.png").unlink()
        (self.project / "figures/a.png").write_bytes(original)
        review = inspect_project_migration(self.project)
        (self.project / PENDING_PATH).mkdir()
        with self.assertRaises(ValueError):
            migrate_project_copy(review, self.home / "pending")
        self.assertTrue((self.project / PENDING_PATH).is_dir())
        (self.project / PENDING_PATH).rmdir()
        (self.project / ".icstex/layouts.json").write_bytes(b"{}")
        with self.assertRaises(ValueError):
            migrate_project_copy(review, self.home / "new-marker")

    def test_candidate_tampering_and_byte_budget_refuse(self):
        from dataclasses import replace
        self.legacy()
        review = inspect_project_migration(self.project)
        forged = replace(review, candidate=review.candidate + (("unexpected.tex", b"not reviewed"),))
        with self.assertRaises(OSError):
            migrate_project_copy(forged, self.home / "forged")
        with patch.object(project_migration, "MAX_TOTAL_BYTES", 1):
            with self.assertRaises(ValueError):
                migrate_project_copy(review, self.home / "too-big")
        self.assertFalse((self.home / "forged").exists())
        self.assertFalse((self.home / "too-big").exists())

    def test_migration_reader_verifies_retained_originals_and_detaches_replaced_draft_targets(self):
        from app.core.project_migration import read_migration_copy
        before = self.legacy()
        review = inspect_project_migration(self.project)
        drafts = [DraftInput("main-draft", "source-text", "main.tex", b"old independent draft"),
                  DraftInput("bib-draft", "source-text", "refs.bib", b"same target draft")]
        result = migrate_project_copy(review, self.home / "readable", drafts=drafts)
        read = read_migration_copy(result.directory)
        self.assertEqual(dict(read.originals), before)
        self.assertEqual([e.target for e in read.copy.info.drafts], [None, "refs.bib"])
        self.assertEqual(dict(read.copy.drafts), {d.id: d.payload for d in drafts})
        retained = result.directory / "recovery-evidence/original/main.tex"
        retained.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            read_migration_copy(result.directory)
        retained.write_bytes(before["main.tex"])
        with self.assertRaises(OSError):
            read_migration_copy(result.directory, expected=read)
        self.assertEqual(self.files(), before)

    def test_migration_reader_rejects_unknown_decisions_and_hidden_unmapped_fields(self):
        from app.core.project_migration import read_migration_copy
        self.legacy()
        path = self.project / ".icstex/blocks.json"
        data = json.loads(path.read_bytes())
        data["customField"] = {"flag": False, "zero": 0}
        path.write_text(json.dumps(data))
        result = migrate_project_copy(inspect_project_migration(self.project), self.home / "readable")
        decision = result.directory / "recovery-evidence/decision.json"
        report = json.loads(decision.read_bytes())
        for changes in ({"version": True}, {"version": 2}, {"unmapped_legacy_fields": []},
                        {"output": []}, {"kind": "source-copy"}, {"unexpected": "field"}):
            with self.subTest(changes=changes):
                decision.write_text(json.dumps(dict(report, **changes)))
                with self.assertRaises(ValueError):
                    read_migration_copy(result.directory)
        report["originals"][0]["path"] = "../outside.tex"
        decision.write_text(json.dumps(report))
        with self.assertRaises(ValueError):
            read_migration_copy(result.directory)

    def test_migration_reader_rechecks_evidence_between_passes(self):
        from app.core.project_migration import read_migration_copy
        self.legacy()
        result = migrate_project_copy(inspect_project_migration(self.project), self.home / "readable")
        real = project_migration._read_file
        changed = False
        def mutate(*args, **kwargs):
            nonlocal changed
            value = real(*args, **kwargs)
            if args[1] == "recovery-evidence/original/main.tex" and not changed:
                changed = True
                (result.directory / args[1]).write_bytes(b"changed between passes")
            return value
        with patch.object(project_migration, "_read_file", side_effect=mutate), self.assertRaises(OSError):
            read_migration_copy(result.directory)

    def test_inventory_warning_survives_explicit_selected_recheck(self):
        self.legacy()
        paths = tuple(self.files())
        with patch.object(project_migration, "checkpoint_candidates", return_value=(paths, ("Synthetic incomplete inventory",))):
            review = inspect_project_migration(self.project)
        result = migrate_project_copy(review, self.home / "warned")
        report = json.loads((result.directory / "recovery-evidence/decision.json").read_bytes())
        self.assertIn("Synthetic incomplete inventory", report["warnings"])
