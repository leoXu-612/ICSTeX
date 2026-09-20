from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest import TestCase
from unittest.mock import patch

from app.core.citation_health import CitationRequest, check_citations, CitationCancelled


class CitationHealthTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.scope = Path(self.temp.name).resolve()
        self.root = self.scope / "main.tex"
        self.root.write_text("\\input{chapters/child}\n\\bibliography{literature/catalog,more}\n")
        (self.scope / "chapters").mkdir()
        (self.scope / "chapters/child.tex").write_text("Text\n\\cite[see][p. 3]{Known,Missing}\n")
        (self.scope / "literature").mkdir()
        (self.scope / "literature/catalog.bib").write_text(
            "@article{Known,title={Known}}\n@book{Duplicate,title={A}}\n@book{Unused,title={U}}\n")
        (self.scope / "more.bib").write_text("@book{Duplicate,title={B}}\n")
        self.request = CitationRequest(("test", 1), self.scope, self.root)

    def issues(self, result, rule):
        return [item for item in result.items if item.rule == rule]

    def test_cross_file_definitions_usage_duplicates_and_missing_are_read_only(self):
        before = {p: p.read_bytes() for p in self.scope.rglob("*") if p.is_file()}
        result = check_citations(self.request)
        self.assertTrue(result.stable)
        self.assertTrue(result.complete)
        missing = self.issues(result, "citation_missing")[0]
        self.assertEqual(missing.key, "Missing")
        self.assertEqual(missing.status, "fail")
        self.assertEqual((missing.locations[0].path, missing.locations[0].line),
                         (self.scope / "chapters/child.tex", 2))
        duplicate = self.issues(result, "key_duplicate")[0]
        self.assertEqual(duplicate.key, "Duplicate")
        self.assertEqual(len(duplicate.locations), 2)
        self.assertIn("Unused", [item.key for item in self.issues(result, "entry_unused")])
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_captured_bib_and_child_drafts_override_disk_without_saving(self):
        draft = "\\cite{DraftOnly}\n"
        result = check_citations(replace(self.request, buffers=(
            (self.scope / "chapters/child.tex", draft),
            (self.scope / "more.bib", "@book{DraftOnly,title={Draft}}\n"))))
        self.assertFalse(self.issues(result, "citation_missing"))
        self.assertFalse(self.issues(result, "key_duplicate"))
        self.assertIn("DraftOnly", [item.key for item in self.issues(result, "entry_used")])
        self.assertNotIn("DraftOnly", (self.scope / "more.bib").read_text())

    def test_missing_bib_and_unknown_macro_never_produce_complete_unused_claims(self):
        (self.scope / "more.bib").unlink()
        result = check_citations(self.request)
        self.assertFalse(result.complete)
        self.assertTrue(self.issues(result, "input_unreadable"))
        self.assertFalse(self.issues(result, "entry_unused"))
        self.assertEqual(self.issues(result, "citation_missing")[0].status, "unknown")

    def test_malformed_bib_is_explicit_and_disables_negative_claims(self):
        (self.scope / "more.bib").write_text("@article{Bad,title {Missing equals}}")
        result = check_citations(self.request)
        self.assertFalse(result.complete)
        self.assertTrue(self.issues(result, "bib_unparsed"))
        self.assertFalse(self.issues(result, "entry_unused"))

    def test_crossref_dependency_and_nocite_all_are_not_unused(self):
        self.root.write_text("\\cite{Child}\n\\bibliography{more}\n")
        (self.scope / "more.bib").write_text(
            '@inproceedings{Child,title={C},crossref="Parent"}\n'
            '@proceedings{Parent,title={P}}\n@book{Other,title={O}}')
        result = check_citations(self.request)
        self.assertEqual([item.key for item in self.issues(result, "entry_unused")], ["Other"])
        self.root.write_text("\\nocite{*}\n\\bibliography{more}\n")
        self.assertFalse(self.issues(check_citations(self.request), "entry_unused"))

    def test_unsafe_bib_path_is_not_read(self):
        with TemporaryDirectory() as outside:
            secret = Path(outside) / "secret.bib"
            secret.write_text("@book{Secret,title={Synthetic}}")
            (self.scope / "more.bib").unlink()
            (self.scope / "more.bib").symlink_to(secret)
            result = check_citations(self.request)
        self.assertFalse(result.complete)
        self.assertNotIn("Secret", [item.key for item in result.items])
        self.assertNotIn(secret, result.watched_paths)

    def test_cancel_and_limits_are_not_passes(self):
        cancel = Event()
        cancel.set()
        with self.assertRaises(CitationCancelled):
            check_citations(self.request, cancel)
        result = check_citations(replace(self.request, max_bytes=10))
        self.assertFalse(result.complete)
        self.assertTrue(self.issues(result, "input_unreadable"))

    def test_change_during_check_invalidates_result_identity(self):
        from app.core import citation_health
        original_parse = citation_health.parse_bibliography
        target = self.scope / "more.bib"

        def changed(text, **kwargs):
            result = original_parse(text, **kwargs)
            target.write_text("@book{New,title={New}}")
            return result

        with patch.object(citation_health, "parse_bibliography", changed):
            result = check_citations(self.request)
        self.assertFalse(result.stable)

    def test_standard_distro_inputs_are_not_missing_project_bibliographies(self):
        self.root.write_text("\\documentclass{article}\n\\usepackage{natbib}\n"
                             "\\cite{Known}\n\\bibliography{literature/catalog}\n")
        result = check_citations(self.request)
        self.assertTrue(result.complete, result.items)
        self.assertIn("Unused", [item.key for item in self.issues(result, "entry_unused")])

    def test_empty_bib_can_be_rechecked_and_missing_key_is_explicit(self):
        self.root.write_text("\\cite{Missing}\n\\bibliography{more}\n")
        (self.scope / "more.bib").write_bytes(b"")
        result = check_citations(self.request)
        self.assertTrue(result.stable)
        self.assertTrue(result.complete)
        self.assertEqual(self.issues(result, "citation_missing")[0].status, "fail")

    def test_manual_bibliography_alias_and_refsections_prevent_false_negative_claims(self):
        variants = (
            ("\\cite{Manual}\n\\bibitem{Manual} text", "@book{Unused,title={U}}"),
            ("\\cite{Alias}", "@book{Original,ids={Alias},title={O}}"),
            ("\\begin{refsection}\\cite{Known}\\end{refsection}", "@book{Unused,title={U}}"),
            ("\\newrefsection\\cite{Known}", "@book{Unused,title={U}}"),
        )
        for tex, bib in variants:
            with self.subTest(tex=tex):
                self.root.write_text(tex + "\n\\bibliography{more}\n")
                (self.scope / "more.bib").write_text(bib)
                result = check_citations(self.request)
                self.assertFalse(result.complete)
                self.assertFalse(self.issues(result, "entry_unused"))
                self.assertTrue(all(item.status == "unknown" for item in self.issues(result, "citation_missing")))

    def test_extensionless_input_is_explicitly_outside_recursive_coverage(self):
        (self.scope / "chapter").write_text(r"\cite{Known}")
        self.root.write_text("\\input{chapter}\n\\bibliography{literature/catalog}\n")
        result = check_citations(self.request)
        self.assertFalse(result.complete)
        self.assertFalse(self.issues(result, "entry_unused"))
        self.assertTrue(self.issues(result, "dependency_unknown"))
