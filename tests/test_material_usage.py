from dataclasses import replace
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest import TestCase
from unittest.mock import patch

from app.core.material_usage import MaterialBaseline, MaterialCancelled, MaterialRequest, check_materials


class MaterialUsageTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="icstex-material-")
        self.addCleanup(self.temp.cleanup)
        self.scope = Path(self.temp.name).resolve()
        self.root = self.scope / "main.tex"
        self.child = self.scope / "child.tex"
        (self.scope / "figures").mkdir()
        self.asset = self.scope / "figures/plot.png"
        self.asset.write_bytes(b"synthetic image bytes")
        self.root.write_text("\\documentclass{article}\n\\graphicspath{{figures/}}\n\\input{child}\n")
        self.child.write_text("Text\n\\includegraphics[width=2cm]{plot}\n")
        self.request = MaterialRequest("request", self.scope, self.root)

    def asset_item(self, result, path=None):
        return next(item for item in result.items if item.path == (path or self.asset))

    def test_root_child_graphicspath_locations_and_no_double_count_or_writes(self):
        before = {path: path.read_bytes() for path in (self.root, self.child, self.asset)}
        result = check_materials(replace(self.request, buffers=((self.child, self.child.read_text()),)))
        self.assertTrue(result.complete, result.items)
        self.assertTrue(result.stable)
        item = self.asset_item(result)
        self.assertEqual(item.rule, "asset_present")
        self.assertEqual([(loc.path, loc.line) for loc in item.locations], [(self.child, 2)])
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertFalse((self.scope / ".icstex").exists())

    def test_comments_and_removed_noncurrent_draft_do_not_count_disk_use(self):
        result = check_materials(replace(self.request, buffers=((self.child, "% \\includegraphics{plot}\nRemoved."),)))
        self.assertTrue(result.complete, result.items)
        item = self.asset_item(result)
        self.assertEqual(item.rule, "asset_unused")
        self.assertEqual(item.status, "suggestion")
        self.assertEqual(item.locations, ())

    def test_unincluded_source_does_not_count_as_active_root_usage(self):
        self.child.write_text("No image here")
        (self.scope / "old-draft.tex").write_text(r"\includegraphics{figures/plot}")
        self.assertEqual(self.asset_item(check_materials(self.request)).rule, "asset_unused")

    def test_missing_and_ambiguous_extensions_are_distinct_from_unused(self):
        self.asset.unlink()
        result = check_materials(self.request)
        self.assertTrue(any(item.rule == "asset_missing" and item.status == "fail" for item in result.items))
        self.asset.write_bytes(b"png")
        (self.scope / "figures/plot.pdf").write_bytes(b"pdf")
        result = check_materials(self.request)
        self.assertFalse(result.complete)
        self.assertTrue(any(item.rule == "asset_ambiguous" for item in result.items))
        self.assertFalse(any(item.rule == "asset_unused" for item in result.items))

    def test_unknown_macro_missing_source_and_bad_encoding_never_imply_unused(self):
        for text in (r"\newcommand{\picture}{\includegraphics{figures/plot}}", r"\input{gone}"):
            with self.subTest(text=text):
                self.root.write_text(text)
                result = check_materials(self.request)
                self.assertFalse(result.complete)
                self.assertFalse(any(item.rule == "asset_unused" for item in result.items))
        self.root.write_bytes(b"\xff\x80\xff")
        result = check_materials(self.request)
        self.assertFalse(result.complete)
        self.assertTrue(any(item.rule == "source_unknown" for item in result.items))

    def test_content_change_uses_digest_not_mtime_and_never_advances_baseline(self):
        baseline = MaterialBaseline(self.asset, hashlib.sha256(self.asset.read_bytes()).hexdigest(), "earlier")
        self.asset.write_bytes(b"changed image bytes")
        result = check_materials(replace(self.request, previous=(baseline,)))
        item = self.asset_item(result)
        self.assertEqual(item.rule, "asset_changed")
        self.assertEqual(item.baseline, baseline)
        self.assertNotEqual(item.digest, baseline.digest)

    def test_one_same_content_candidate_is_not_an_automatic_move(self):
        self.child.write_text(r"\includegraphics{figures/plot.png}")
        original = self.asset.read_bytes()
        baseline = MaterialBaseline(self.asset, hashlib.sha256(original).hexdigest(), "earlier")
        self.asset.unlink()
        candidate = self.scope / "figures/new.png"
        candidate.write_bytes(original)
        result = check_materials(replace(self.request, previous=(baseline,)))
        item = next(item for item in result.items if item.rule == "asset_candidate")
        self.assertEqual(item.candidates, (candidate,))
        self.assertEqual(item.baseline, baseline)
        self.assertFalse(self.asset.exists())
        (self.scope / "figures/another.png").write_bytes(original)
        result = check_materials(replace(self.request, previous=(baseline,)))
        self.assertTrue(any(item.rule == "asset_ambiguous" for item in result.items))

    def test_links_and_internal_inputs_are_not_read_or_suggested_as_candidates(self):
        with TemporaryDirectory() as outside:
            secret = Path(outside) / "outside.png"
            secret.write_bytes(b"synthetic outside bytes")
            self.asset.unlink()
            self.asset.symlink_to(secret)
            (self.scope / ".git").mkdir()
            (self.scope / ".git" / "secret.png").write_bytes(b"synthetic internal bytes")
            result = check_materials(self.request)
        self.assertFalse(result.complete)
        self.assertNotIn(secret, result.watched_paths)
        self.assertFalse(any(path.name == "secret.png" for path, _digest in result.assets))

    def test_cancel_byte_and_directory_limits_keep_unknown_visible(self):
        cancelled = Event()
        cancelled.set()
        with self.assertRaises(MaterialCancelled):
            check_materials(self.request, cancelled)
        for request in (replace(self.request, max_source_bytes=5),
                        replace(self.request, max_asset_bytes=3),
                        replace(self.request, max_scan_entries=1)):
            result = check_materials(request)
            self.assertFalse(result.complete)
            self.assertTrue(any(item.status == "unknown" for item in result.items))

    def test_changed_during_final_recheck_is_not_accepted(self):
        from app.core import material_usage
        original = material_usage.hash_file
        reads = []

        def changed(path, **kwargs):
            value = original(path, **kwargs)
            reads.append(path)
            if len(reads) == 1:
                self.asset.write_bytes(b"changed after initial read")
            return value

        with patch.object(material_usage, "hash_file", changed):
            result = check_materials(self.request)
        self.assertFalse(result.stable)

    def test_dynamic_graphicspath_and_custom_extension_rules_remain_unknown(self):
        for tex in (r"\graphicspath{\externalPaths}\includegraphics{plot}",
                    r"\DeclareGraphicsExtensions{.other}\includegraphics{plot}", r"\epsfig{file=plot.png}"):
            with self.subTest(tex=tex):
                self.root.write_text(tex)
                result = check_materials(self.request)
                self.assertFalse(result.complete)
                self.assertFalse(any(item.rule == "asset_unused" for item in result.items))
                self.assertTrue(any(item.rule == "source_unknown" for item in result.items))

    def test_literal_svg_and_pdf_commands_have_source_locations(self):
        vector, pdf = self.scope / "drawing.svg", self.scope / "appendix.pdf"
        vector.write_bytes(b"synthetic svg")
        pdf.write_bytes(b"synthetic pdf")
        self.root.write_text("\\includesvg[width=2cm]{drawing}\n\\includepdf[pages=-]{appendix}\n")
        result = check_materials(self.request)
        self.assertTrue(result.complete, result.items)
        for path, line in ((vector, 1), (pdf, 2)):
            self.assertEqual([(loc.path, loc.line) for loc in self.asset_item(result, path).locations], [(self.root, line)])

    def test_extensionless_and_multiple_path_scopes_are_explicitly_unknown(self):
        (self.scope / "child").write_text(r"\includegraphics{plot}")
        result = check_materials(self.request)
        self.assertFalse(result.complete)
        (self.scope / "child").unlink()
        self.child.write_text(r"\graphicspath{{other/}}\includegraphics{plot}")
        result = check_materials(self.request)
        self.assertFalse(result.complete)

    def test_original_reappearing_during_candidate_lookup_invalidates_result(self):
        from app.core import material_usage
        self.child.write_text(r"\includegraphics{figures/plot.png}")
        raw = self.asset.read_bytes()
        baseline = MaterialBaseline(self.asset, hashlib.sha256(raw).hexdigest(), "earlier")
        self.asset.unlink()
        candidate = self.scope / "figures/new.png"
        candidate.write_bytes(raw)
        original = material_usage.hash_file

        def reappear(path, **kwargs):
            result = original(path, **kwargs)
            if path == candidate:
                self.asset.write_bytes(raw)
            return result

        with patch.object(material_usage, "hash_file", reappear):
            result = check_materials(replace(self.request, previous=(baseline,)))
        self.assertFalse(result.stable)
