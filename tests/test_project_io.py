from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.blocks.ids import new_block_id
from app.core.blocks.layout import LayoutNode, block_slot
from app.core.blocks.model import Semantic, content_for_text
from app.core.blocks.project_io import load_block_project
from app.core.blocks.registry import BlockRegistry, CreateBlockInput


class ProjectIOTests(TestCase):
    def test_load_empty_project(self) -> None:
        with TemporaryDirectory() as directory:
            project = load_block_project(Path(directory))
            self.assertEqual(project["registry"].blocks(), [])
            self.assertIsNone(project["layout"])
            self.assertEqual(project["theme"].id, "doc_default")

    def test_load_registry_layout_and_theme(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            metadata = project / ".icstex"
            metadata.mkdir(parents=True)
            styles = project / "styles"
            styles.mkdir()
            registry = BlockRegistry()
            registry.create(
                CreateBlockInput(
                    type="text",
                    alias="a",
                    semantic=Semantic(role="text"),
                    content=content_for_text("hello"),
                )
            )
            (metadata / "blocks.json").write_text(
                json.dumps(
                    {"format": "icstex-blocks", "schemaVersion": "1.0.0", "blocks": [b.to_dict() for b in registry.blocks()]},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            layout = LayoutNode(id="lyt_row", kind="row", children=(block_slot(new_block_id()),))
            (metadata / "layouts.json").write_text(
                json.dumps({"schemaVersion": "1.0.0", "layouts": [layout.to_dict()]}),
                encoding="utf-8",
            )
            (styles / "document-theme.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": "1.0.0",
                        "kind": "document-theme",
                        "id": "doc_loaded",
                        "name": "Loaded",
                        "page": {"size": "a4", "orientation": "portrait", "columns": 1, "margin": {}},
                        "typography": {"textFamily": "", "mathFamily": "", "monoFamily": "", "baseSizePt": 11, "lineSpacing": 1.0},
                    }
                ),
                encoding="utf-8",
            )

            loaded = load_block_project(project)

            self.assertEqual(len(loaded["registry"].blocks()), 1)
            self.assertEqual(loaded["registry"].blocks()[0].alias, "a")
            self.assertIsNotNone(loaded["layout"])
            self.assertEqual(loaded["theme"].id, "doc_loaded")
