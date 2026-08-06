"""Migration framework and legacy migrators (Modular Layout MVP Sprint 1).

Migration invariants from the task list: deterministic input/output, never
overwrite the original directly, migrate and validate in a temporary file,
atomic replace on success, save a backup first, preserve unknown fields in
``extensions``, and make re-runs safe via a recorded migration version.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import shutil
from pathlib import Path
import time

from app.core.blocks.ids import new_block_id, new_instance_id, new_layout_id
from app.core.blocks.schema import validate_block, validate_layout


class MigrationError(ValueError):
    pass


@dataclass(frozen=True)
class MigrationPlan:
    version: int
    description: str

    def apply(self, data: dict) -> dict:
        raise NotImplementedError


class SideBySideFigureMigration(MigrationPlan):
    """Legacy side-by-side figure objects -> two Image Blocks + a Row layout."""

    def __init__(self) -> None:
        super().__init__(version=1, description="并排图片迁移为两个 Image Block + Row 布局")

    def apply(self, data: dict) -> dict:
        legacy = data.get("legacySideBySideFigures", [])
        if not legacy:
            return data
        blocks = list(data.get("blocks", []))
        layouts = list(data.get("layouts", []))
        for index, entry in enumerate(legacy):
            left_id = new_block_id()
            right_id = new_block_id()
            blocks.extend(
                [
                    {
                        "schemaVersion": "1.0.0",
                        "id": left_id,
                        "type": "image",
                        "alias": f"side-by-side-{index}-left",
                        "semantic": {
                            "role": "figure",
                            "label": None,
                            "caption": {"text": str(entry.get("leftCaption") or "")},
                            "numbering": "auto",
                        },
                        "content": {"source": str(entry["leftImage"]), "width": None},
                        "references": [],
                        "provenance": {"kind": "imported", "sourceId": None, "importedAt": None},
                        "revision": 1,
                        "metadata": {},
                        "extensions": {"legacyPlacement": entry.get("placement")},
                    },
                    {
                        "schemaVersion": "1.0.0",
                        "id": right_id,
                        "type": "image",
                        "alias": f"side-by-side-{index}-right",
                        "semantic": {
                            "role": "figure",
                            "label": entry.get("label") if index == 0 else None,
                            "caption": {"text": str(entry.get("rightCaption") or "")},
                            "numbering": "auto",
                        },
                        "content": {"source": str(entry["rightImage"]), "width": None},
                        "references": [],
                        "provenance": {"kind": "imported", "sourceId": None, "importedAt": None},
                        "revision": 1,
                        "metadata": {},
                        "extensions": {"legacyPlacement": entry.get("placement")},
                    },
                ]
            )
            layouts.append(
                {
                    "schemaVersion": "1.0.0",
                    "id": new_layout_id(),
                    "kind": "row",
                    "gap": {"value": 8, "unit": "mm"},
                    "alignment": "top",
                    "fallback": {"strategy": "stack"},
                    "children": [
                        {
                            "instanceId": new_instance_id(),
                            "kind": "block",
                            "blockId": left_id,
                            "weight": 1,
                            "minWidthPt": 120,
                        },
                        {
                            "instanceId": new_instance_id(),
                            "kind": "block",
                            "blockId": right_id,
                            "weight": 1,
                            "minWidthPt": 120,
                        },
                    ],
                }
            )
        data["blocks"] = blocks
        data["layouts"] = layouts
        data["legacySideBySideFiguresMigrated"] = True
        return data


class RawLatexMigration(MigrationPlan):
    """Legacy LaTeX snippets -> RawLatexBlock (text preserved, no parsing)."""

    def __init__(self) -> None:
        super().__init__(version=1, description="旧 LaTeX 片段迁移为 RawLatexBlock")

    def apply(self, data: dict) -> dict:
        legacy = data.get("legacyLatexSnippets", [])
        if not legacy:
            return data
        blocks = list(data.get("blocks", []))
        for index, entry in enumerate(legacy):
            blocks.append(
                {
                    "schemaVersion": "1.0.0",
                    "id": new_block_id(),
                    "type": "rawLatex",
                    "alias": str(entry.get("alias") or f"legacy-latex-{index}"),
                    "semantic": {"role": "raw-latex", "label": None, "caption": None, "numbering": "none"},
                    "content": {"latex": str(entry["latex"]), "trusted": False},
                    "references": [],
                    "provenance": {"kind": "imported", "sourceId": None, "importedAt": None},
                    "revision": 1,
                    "metadata": {},
                    "extensions": {},
                }
            )
        data["blocks"] = blocks
        data["legacyLatexSnippetsMigrated"] = True
        return data


class MigrationRunner:
    """Applies ordered MigrationPlans with backup, temp validation, rollback."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = Path(project_dir).expanduser().resolve()
        self.blocks_path = self.project_dir / ".icstex" / "blocks.json"
        self.backups_dir = self.project_dir / ".icstex" / "backups"
        self.log_path = self.project_dir / ".icstex" / "migrations.log"

    def run(self, plans: list[MigrationPlan]) -> dict:
        if not self.blocks_path.is_file():
            raise MigrationError("缺少 .icstex/blocks.json，无法迁移。")
        try:
            data = json.loads(self.blocks_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise MigrationError(f"Block 数据无法解析：{exc}") from exc

        applied_version = int(data.get("migrationVersion", 0) or 0)
        pending = sorted(
            [plan for plan in plans if plan.version > applied_version],
            key=lambda plan: plan.version,
        )
        if not pending:
            return data

        self._backup(data)
        working = json.loads(json.dumps(data))  # deep copy for rollback isolation
        failed_version: int | None = None
        try:
            for plan in pending:
                failed_version = plan.version
                working = plan.apply(working)
                working["migrationVersion"] = plan.version
                self._validate(working)
        except Exception as exc:
            self._log(f"FAILED at version {failed_version} : {exc}")
            raise MigrationError(f"迁移失败（已保留原项目）：{exc}") from exc

        self._write_atomic(working)
        self._log("OK versions=" + ",".join(str(plan.version) for plan in pending))
        return working

    def _backup(self, data: dict) -> None:
        stamp = time.strftime("%Y%m%dT%H%M%S", time.localtime())
        backup_dir = self.backups_dir / f"before-{stamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        (backup_dir / "blocks.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _validate(self, data: dict) -> None:
        for block in data.get("blocks", []):
            issues = validate_block(block)
            if issues:
                raise MigrationError("迁移结果 Schema 校验失败：" + "; ".join(issues[:3]))
        for layout in data.get("layouts", []):
            issues = validate_layout(layout)
            if issues:
                raise MigrationError("布局 Schema 校验失败：" + "; ".join(issues[:3]))

    def _write_atomic(self, data: dict) -> None:
        self.blocks_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.blocks_path.with_name(self.blocks_path.name + ".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.blocks_path)

    def _log(self, line: str) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime())} {line}\n")
        except OSError:
            pass


def legacy_fixture() -> dict:
    """A deterministic legacy project fixture used by migrator tests."""

    return {
        "format": "icstex-legacy-project",
        "legacySideBySideFigures": [
            {
                "leftImage": "figures/a.png",
                "rightImage": "figures/b.png",
                "leftCaption": "A",
                "rightCaption": "B",
                "label": "fig:ab",
                "placement": "htbp",
            }
        ],
        "legacyLatexSnippets": [{"alias": "old-formula", "latex": "E=mc^2"}],
    }
