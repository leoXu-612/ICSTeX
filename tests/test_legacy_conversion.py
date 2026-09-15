from copy import deepcopy
import json
from unittest import TestCase

from app.core.blocks.migration import (
    MigrationError, RawLatexMigration, SideBySideFigureMigration,
    convert_legacy_document, legacy_fixture,
)
from app.core.project_recovery import parse_block_model


def encoded(data):
    return json.dumps(data, ensure_ascii=False, indent=1).replace("\n", "\r\n").encode()


class LegacyConversionTests(TestCase):
    def test_deterministic_complete_model_and_original_bytes(self):
        raw = encoded(legacy_fixture())
        one = convert_legacy_document(raw)
        two = convert_legacy_document(raw)
        self.assertEqual(one, two)
        self.assertEqual(one.original, raw)
        loaded = parse_block_model(one.model)
        self.assertEqual(len(loaded["registry"].blocks()), 3)
        self.assertEqual(loaded["layout"].kind, "column")
        row, snippet = loaded["layout"].children
        self.assertEqual(len(row.children), 2)
        self.assertEqual(loaded["registry"].get(snippet.blockId).content["latex"], "E=mc^2")

    def test_plans_are_pure_and_independently_repeatable(self):
        original = legacy_fixture()
        before = deepcopy(original)
        for plan in (SideBySideFigureMigration(), RawLatexMigration()):
            first = plan.apply(original)
            self.assertEqual(original, before)
            self.assertEqual(plan.apply(original), first)
            self.assertEqual(plan.apply(first), first)

    def test_partial_old_migration_keeps_existing_ids_and_adds_missing_plan(self):
        original = legacy_fixture()
        for done in (RawLatexMigration(), SideBySideFigureMigration()):
            partial = done.apply(original)
            partial["migrationVersion"] = 1
            existing = {b["id"]: b for b in partial["blocks"]}
            result = convert_legacy_document(encoded(partial))
            self.assertEqual(len(result.model["blocks"]), 3)
            actual = {b["id"]: b for b in result.model["blocks"]}
            self.assertTrue(existing.keys() <= actual.keys())
            for identity, block in existing.items():
                self.assertEqual(actual[identity], block)

    def test_false_completed_marker_is_rejected_not_silently_dropped(self):
        original = legacy_fixture()
        original["legacyLatexSnippetsMigrated"] = True
        with self.assertRaises(MigrationError):
            convert_legacy_document(encoded(original))

    def test_unknown_fields_and_verbatim_latex_remain_available(self):
        original = legacy_fixture()
        original["customDocumentMetadata"] = {"zero": 0, "flag": False}
        entry = original["legacyLatexSnippets"][0]
        entry["latex"] = "  \\unknown{value}% comment\r\n next\t"
        entry["custom"] = {"zero": 0, "flag": False}
        result = convert_legacy_document(encoded(original))
        block = next(b for b in result.model["blocks"] if b["type"] == "rawLatex")
        self.assertEqual(block["content"]["latex"], entry["latex"])
        self.assertFalse(block["content"]["trusted"])
        self.assertEqual(block["extensions"]["legacyInput"], entry)
        self.assertIn("customDocumentMetadata", result.unmapped_keys)
        self.assertEqual(json.loads(result.original), original)

    def test_unknown_formats_versions_malformed_types_and_duplicates_refuse(self):
        for changes in ({"format": "unknown"}, {"schemaVersion": "99.0.0"},
                        {"migrationVersion": 2}, {"migrationVersion": True},
                        {"legacyLatexSnippets": [{"latex": 0}]},
                        {"legacySideBySideFigures": [{"leftImage": "../outside.png", "rightImage": "b.png"}]},
                        {"legacySideBySideFigures": "wrong type"}):
            with self.subTest(changes=changes):
                original = legacy_fixture()
                original.update(changes)
                with self.assertRaises(MigrationError):
                    convert_legacy_document(encoded(original))
        with self.assertRaises(MigrationError):
            convert_legacy_document(b'{"format":"icstex-legacy-project","format":"icstex-legacy-project"}')

    def test_unknown_existing_block_fields_and_unresolved_layout_refuse(self):
        original = RawLatexMigration().apply(legacy_fixture())
        original["blocks"][0]["futureField"] = True
        with self.assertRaises(MigrationError):
            convert_legacy_document(encoded(original))
        original = SideBySideFigureMigration().apply(legacy_fixture())
        original["layouts"][0]["children"][0]["blockId"] = "blk_MISSING"
        with self.assertRaises(MigrationError):
            convert_legacy_document(encoded(original))

    def test_duplicate_aliases_nonfinite_data_and_layout_instances_refuse(self):
        original = legacy_fixture()
        original["legacyLatexSnippets"] *= 2
        with self.assertRaises(MigrationError):
            convert_legacy_document(encoded(original))
        with self.assertRaises(MigrationError):
            convert_legacy_document(b'{"format":"icstex-legacy-project","future":1e999}')
        original = SideBySideFigureMigration().apply(legacy_fixture())
        children = original["layouts"][0]["children"]
        children[1]["instanceId"] = children[0]["instanceId"]
        with self.assertRaises(MigrationError):
            convert_legacy_document(encoded(original))

    def test_real_old_optional_defaults_and_non_deterministic_ids_are_preserved(self):
        original = SideBySideFigureMigration().apply(legacy_fixture())
        prior = original["blocks"][0]
        old_id = "blk_01K0000000ABCDEFGHIJKLMNOP"
        previous_id = prior["id"]
        prior["id"] = old_id
        prior["semantic"]["caption"].pop("shortText")
        original["layouts"][0].pop("keepTogether")
        for slot in original["layouts"][0]["children"]:
            if slot["blockId"] == previous_id:
                slot["blockId"] = old_id
        original["migrationVersion"] = 1
        converted = convert_legacy_document(encoded(original))
        block = next(b for b in converted.model["blocks"] if b["id"] == old_id)
        self.assertEqual(block["content"], prior["content"])
        self.assertEqual(block["extensions"], prior["extensions"])
        self.assertEqual(converted.model["layout"]["children"][0]["id"], original["layouts"][0]["id"])
