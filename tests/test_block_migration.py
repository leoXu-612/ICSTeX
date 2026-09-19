from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.blocks.migration import (
    MigrationError,
    MigrationPlan,
    MigrationRunner,
    RawLatexMigration,
    SideBySideFigureMigration,
    legacy_fixture,
)
from app.core.blocks.schema import validate_block, validate_layout


class _FailingMigration(MigrationPlan):
    def __init__(self) -> None:
        super().__init__(version=2, description="故意失败的迁移")

    def apply(self, data: dict) -> dict:
        data["blocks"].append({"bad": "schema"})
        return data


class MigrationRunnerTests(TestCase):
    def _project_with_legacy(self) -> tuple[Path, Path]:
        project = Path(self._tmp_name)
        (project / ".icstex").mkdir(parents=True)
        path = project / ".icstex" / "blocks.json"
        path.write_text(json.dumps(legacy_fixture(), ensure_ascii=False), encoding="utf-8")
        return project, path

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._tmp_name = self._tmp.name

    def test_side_by_side_and_raw_latex_migrate_deterministically(self) -> None:
        project, path = self._project_with_legacy()
        runner = MigrationRunner(project)

        first = runner.run([SideBySideFigureMigration(), RawLatexMigration()])
        second = runner.run([SideBySideFigureMigration(), RawLatexMigration()])

        self.assertEqual(first["migrationVersion"], 1)
        self.assertEqual(len(first["blocks"]), 3)  # 2 images + 1 raw latex
        self.assertEqual(len(first["layouts"]), 1)
        for block in first["blocks"]:
            self.assertEqual(validate_block(block), [])
        self.assertEqual(validate_layout(first["layouts"][0]), [])
        # Re-run is safe and produces the same output.
        self.assertEqual(second["blocks"], first["blocks"])
        self.assertEqual(second["layouts"], first["layouts"])
        self.assertTrue(path.exists())

    def test_backup_created_before_migration(self) -> None:
        project, _path = self._project_with_legacy()
        runner = MigrationRunner(project)
        runner.run([RawLatexMigration()])

        backups = list((project / ".icstex" / "backups").glob("before-*/blocks.json"))
        self.assertEqual(len(backups), 1)
        backup_data = json.loads(backups[0].read_text(encoding="utf-8"))
        self.assertIn("legacyLatexSnippets", backup_data)

    def test_failed_migration_preserves_original(self) -> None:
        project, path = self._project_with_legacy()
        original = path.read_text(encoding="utf-8")
        runner = MigrationRunner(project)

        with self.assertRaises(MigrationError):
            runner.run([RawLatexMigration(), _FailingMigration()])

        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertFalse(path.with_name(path.name + ".tmp").exists())
        log = (project / ".icstex" / "migrations.log").read_text(encoding="utf-8")
        self.assertIn("FAILED at version 2", log)

    def test_no_pending_plans_is_noop(self) -> None:
        project, path = self._project_with_legacy()
        runner = MigrationRunner(project)
        runner.run([RawLatexMigration()])
        after_first = path.read_text(encoding="utf-8")

        result = runner.run([RawLatexMigration()])
        self.assertEqual(result["migrationVersion"], 1)
        self.assertEqual(path.read_text(encoding="utf-8"), after_first)

    def test_missing_blocks_file_raises(self) -> None:
        project = Path(self._tmp_name) / "empty"
        project.mkdir(exist_ok=True)
        with self.assertRaises(MigrationError):
            MigrationRunner(project).run([RawLatexMigration()])
