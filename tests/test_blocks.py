from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.blocks.ids import new_block_id, new_id
from app.core.blocks.model import (
    BLOCK_TYPES,
    Block,
    BlockReference,
    Caption,
    Provenance,
    Semantic,
    content_for_heading,
    content_for_list,
    content_for_quote,
    content_for_raw_latex,
    content_for_text,
)
from app.core.blocks.registry import (
    BlockError,
    BlockRegistry,
    CreateBlockInput,
)
from app.core.blocks.schema import (
    CONTENT_SCHEMAS,
    validate_block,
    validate_layout,
    validate_project,
)
from app.core.blocks.store import BlockStore, BlockStoreError


def valid_block_dict(block_type: str = "text", **overrides: object) -> dict:
    content = {
        "text": {"format": "plain", "text": "Hello"},
        "heading": {"text": "Title", "level": 1},
        "quote": {"text": "A quote"},
        "list": {"ordered": False, "items": ["a", "b"]},
        "rawLatex": {"latex": "\\textbf{x}", "trusted": False},
        "formula": {
            "format": "icstex-formula-ast",
            "astVersion": "1.0.0",
            "ast": {"kind": "symbol", "value": "E"},
            "latexCache": "E",
        },
        "image": {"source": "figures/a.png"},
        "table": {
            "tableVersion": "1.0.0",
            "columns": [],
            "rows": [],
            "header": {"rowCount": 1, "repeatOnPageBreak": True},
            "merges": [],
            "notes": [],
        },
    }[block_type]
    data = {
        "schemaVersion": "1.0.0",
        "id": new_block_id(),
        "type": block_type,
        "alias": f"block-{block_type}",
        "semantic": {"role": "figure" if block_type == "image" else block_type, "label": None, "caption": None, "numbering": "auto"},
        "content": content,
        "references": [],
        "provenance": {"kind": "created", "sourceId": None, "importedAt": None},
        "revision": 1,
        "metadata": {},
        "extensions": {},
    }
    data.update(overrides)
    return data


class BlockSchemaTests(TestCase):
    def test_all_block_types_validate(self) -> None:
        for block_type in BLOCK_TYPES:
            with self.subTest(block_type=block_type):
                self.assertEqual(validate_block(valid_block_dict(block_type)), [])

    def test_missing_required_field_fails(self) -> None:
        data = valid_block_dict()
        del data["revision"]
        issues = validate_block(data)
        self.assertTrue(any("revision" in issue for issue in issues))

    def test_unknown_type_fails(self) -> None:
        data = valid_block_dict()
        data["type"] = "video"
        self.assertTrue(validate_block(data))

    def test_unknown_schema_version_fails(self) -> None:
        data = valid_block_dict()
        data["schemaVersion"] = "9.9.9"
        self.assertTrue(validate_block(data))

    def test_content_schema_constraints(self) -> None:
        data = valid_block_dict("text")
        data["content"] = {"format": "plain"}
        self.assertTrue(validate_block(data))

    def test_project_and_layout_schemas(self) -> None:
        project = {
            "projectSchemaVersion": "1.0.0",
            "minimumAppVersion": "0.8.0",
            "blockSchemaVersion": "1.0.0",
            "layoutSchemaVersion": "1.0.0",
            "themeSchemaVersion": "1.0.0",
        }
        self.assertEqual(validate_project(project), [])
        del project["minimumAppVersion"]
        self.assertTrue(validate_project(project))

        layout = {
            "schemaVersion": "1.0.0",
            "id": "lyt_row",
            "kind": "row",
            "children": [
                {"instanceId": "ins_a", "kind": "block", "blockId": new_block_id(), "weight": 1, "minWidthPt": 10}
            ],
        }
        self.assertEqual(validate_layout(layout), [])
        layout["children"][0]["kind"] = "video"
        self.assertTrue(validate_layout(layout))

    def test_content_schemas_are_json_serializable(self) -> None:
        for schema in CONTENT_SCHEMAS.values():
            json.dumps(schema)


class BlockIdTests(TestCase):
    def test_id_shape_and_prefixes(self) -> None:
        block_id = new_block_id()
        self.assertTrue(block_id.startswith("blk_"))
        self.assertEqual(len(block_id), 4 + 26)
        self.assertTrue(new_id("lyt").startswith("lyt_"))
        self.assertTrue(new_id("ins").startswith("ins_"))

    def test_ids_are_stable_per_instance(self) -> None:
        registry = BlockRegistry()
        block = registry.create(CreateBlockInput(type="text", alias="a", content=content_for_text("x")))
        self.assertEqual(registry.get(block.id).id, block.id)


class BlockRegistryTests(TestCase):
    def _registry_with_reference(self) -> tuple[BlockRegistry, Block, Block]:
        registry = BlockRegistry()
        target = registry.create(
            CreateBlockInput(
                type="image",
                alias="apparatus",
                semantic=Semantic(role="figure", label="fig:apparatus", caption=Caption("装置")),
                content={"source": "figures/a.png"},
            )
        )
        source = registry.create(
            CreateBlockInput(
                type="text",
                alias="analysis",
                content=content_for_text("见装置"),
                references=[BlockReference(targetBlockId=target.id, kind="cross-reference")],
            )
        )
        return registry, target, source

    def test_rename_alias_preserves_id_and_references(self) -> None:
        registry, target, source = self._registry_with_reference()
        old_id = target.id
        reference_before = source.references[0]

        registry.rename_alias(target.id, "fig-renamed")

        self.assertEqual(registry.get(old_id).id, old_id)
        self.assertEqual(registry.get(old_id).alias, "fig-renamed")
        self.assertEqual(registry.get(source.id).references[0], reference_before)

    def test_update_bumps_revision_and_immutable_id(self) -> None:
        registry = BlockRegistry()
        block = registry.create(CreateBlockInput(type="text", alias="a", content=content_for_text("x")))
        updated = registry.update(block.id, {"content": content_for_text("y")})
        self.assertEqual(updated.revision, 2)
        self.assertEqual(updated.id, block.id)

    def test_remove_reject_if_referenced(self) -> None:
        registry, target, _source = self._registry_with_reference()
        with self.assertRaises(BlockError):
            registry.remove(target.id, "reject-if-referenced")
        self.assertIsNotNone(registry.get(target.id))

    def test_remove_replace_with_placeholder_rewrites_references(self) -> None:
        registry, target, source = self._registry_with_reference()
        registry.remove(target.id, "replace-with-placeholder")

        self.assertIsNone(registry.get(target.id))
        self.assertEqual(len(registry.find_references_to(target.id)), 0)
        new_reference = registry.get(source.id).references[0]
        self.assertNotEqual(new_reference.targetBlockId, target.id)
        self.assertIsNotNone(registry.get(new_reference.targetBlockId))

    def test_find_references_to(self) -> None:
        registry, target, _source = self._registry_with_reference()
        locations = registry.find_references_to(target.id)
        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].referrer_alias, "analysis")

    def test_duplicate_label_rejected(self) -> None:
        registry = BlockRegistry()
        registry.create(CreateBlockInput(type="image", alias="a", semantic=Semantic(role="figure", label="fig:x"), content={"source": "a.png"}))
        with self.assertRaises(BlockError):
            registry.create(CreateBlockInput(type="image", alias="b", semantic=Semantic(role="figure", label="fig:x"), content={"source": "b.png"}))

    def test_validate_all_reports_dangling_reference(self) -> None:
        registry, target, _source = self._registry_with_reference()
        del registry._blocks[target.id]
        issues = registry.validate_all()
        self.assertTrue(any(issue.code == "REF_TARGET_MISSING" for issue in issues))

    def test_validate_all_reports_empty_alias_and_schema(self) -> None:
        registry = BlockRegistry()
        block = registry.create(CreateBlockInput(type="text", alias="a", content=content_for_text("x")))
        block.alias = ""
        block.type = "video"
        codes = {issue.code for issue in registry.validate_all()}
        self.assertIn("BLOCK_ALIAS_EMPTY", codes)
        self.assertIn("BLOCK_SCHEMA", codes)


class BlockStoreTests(TestCase):
    def test_save_load_round_trip_preserves_ids(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / ".icstex" / "blocks.json"
            registry = BlockRegistry()
            first = registry.create(CreateBlockInput(type="text", alias="a", content=content_for_text("hello")))
            store = BlockStore(path)
            store.save(registry)

            loaded = store.load()
            self.assertEqual(loaded.get(first.id).id, first.id)
            self.assertEqual(loaded.get(first.id).content, {"format": "plain", "text": "hello"})
            self.assertFalse(path.with_name(path.name + ".tmp").exists())

    def test_load_rejects_invalid_schema_data(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "blocks.json"
            path.write_text(
                json.dumps(
                    {
                        "format": "icstex-blocks",
                        "schemaVersion": "1.0.0",
                        "blocks": [valid_block_dict("text", revision="not-an-int")],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(BlockStoreError):
                BlockStore(path).load()

    def test_save_rejects_invalid_registry(self) -> None:
        with TemporaryDirectory() as directory:
            registry = BlockRegistry()
            block = registry.create(CreateBlockInput(type="text", alias="a", content=content_for_text("x")))
            block.type = "video"
            with self.assertRaises(BlockStoreError):
                BlockStore(Path(directory) / "blocks.json").save(registry)

    def test_missing_store_loads_empty(self) -> None:
        with TemporaryDirectory() as directory:
            registry = BlockStore(Path(directory) / "blocks.json").load()
            self.assertEqual(registry.blocks(), [])


class BlockModelHelpersTests(TestCase):
    def test_content_helpers(self) -> None:
        self.assertEqual(content_for_heading("T", 3), {"text": "T", "level": 3})
        self.assertEqual(content_for_list(["a"], ordered=True), {"ordered": True, "items": ["a"]})
        self.assertEqual(content_for_raw_latex("\\alpha"), {"latex": "\\alpha", "trusted": False})
        self.assertEqual(content_for_quote("q"), {"text": "q"})
        data = valid_block_dict()
        self.assertEqual(Block.from_dict(data).id, data["id"])
