"""Historical pre-fix probe, retained to explain the original defect receipt.

Requires the old migration implementation. Current code deliberately refuses the
in-place run; use probe_project_migration.py to verify the replacement workflow.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.blocks.migration import (
    MigrationRunner, RawLatexMigration, SideBySideFigureMigration, legacy_fixture,
)
from app.core.blocks.store import BlockStore, BlockStoreError


def observe():
    fixture = legacy_fixture()
    one = RawLatexMigration().apply(deepcopy(fixture))
    two = RawLatexMigration().apply(deepcopy(fixture))
    evidence = {"independent_identical_input_produces_different_ids": one != two}
    with TemporaryDirectory(prefix="icstex-legacy-orientation-") as temporary:
        home = Path(temporary)
        for name in ("original", "incremental", "unknown"):
            project = home / name
            metadata = project / ".icstex"
            metadata.mkdir(parents=True)
            data = deepcopy(fixture)
            if name == "unknown":
                data["format"] = "unknown-future-format"
                data["schemaVersion"] = "999.0.0"
            raw = json.dumps(data, ensure_ascii=False, indent=1).replace("\n", "\r\n").encode()
            path = metadata / "blocks.json"
            path.write_bytes(raw)
            runner = MigrationRunner(project)
            result = runner.run([RawLatexMigration()])
            if name == "original":
                evidence["original_blocks_json_replaced"] = path.read_bytes() != raw
                backup = next((metadata / "backups").glob("before-*/blocks.json"))
                evidence["backup_not_raw_byte_equal"] = backup.read_bytes() != raw
                try:
                    BlockStore.from_bytes(path.read_bytes())
                except BlockStoreError:
                    evidence["successful_runner_output_rejected_by_real_block_loader"] = True
                else:
                    evidence["successful_runner_output_rejected_by_real_block_loader"] = False
            elif name == "incremental":
                second = runner.run([SideBySideFigureMigration(), RawLatexMigration()])
                evidence["shared_version_skips_other_unapplied_plan"] = (
                    second == result and "legacySideBySideFiguresMigrated" not in second)
            else:
                evidence["unknown_future_format_was_rewritten"] = path.read_bytes() != raw
    assert all(evidence.values()), evidence
    print(json.dumps({"observed_gaps": evidence, "synthetic_only": True,
                      "status": "reproduced existing gaps; NOT migration acceptance"}, indent=2))


if __name__ == "__main__":
    observe()
