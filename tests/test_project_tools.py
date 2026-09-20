from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from app.core.project_tools import (
    BIBLIOGRAPHY_LINE,
    BibEntrySpec,
    append_bib_import,
    ProjectInitSpec,
    append_bib_entry,
    bib_import_from_text,
    bib_entry_snippet,
    bib_keys,
    fetch_bib_online,
    citation_snippet,
    duplicate_labels,
    ensure_bibliography,
    initialize_project,
    reference_snippet,
    sanitize_project_name,
    scan_citations,
    scan_labels,
    undefined_citations,
    undefined_references,
)


class ProjectToolsTests(TestCase):
    def test_new_project_preserves_chinese_name_and_selected_profile(self):
        from app.core.project_profile import ProjectProfile, load_profile
        with TemporaryDirectory() as directory:
            profile = ProjectProfile(template="chinese_xelatex_article", engine="xelatex")
            project = initialize_project(ProjectInitSpec(Path(directory), "中文 论文", "chinese_xelatex_article", profile))
            self.assertEqual(project.root_dir.name, "中文 论文")
            self.assertEqual(load_profile(project.root_dir).profile, profile)
            self.assertIn("ctexart", project.tex_file.read_text())

    def test_invalid_template_or_profile_creates_nothing(self):
        from app.core.project_profile import ProjectProfile
        with TemporaryDirectory() as directory:
            parent = Path(directory)
            for spec in (ProjectInitSpec(parent, "New", "not-a-template"),
                         ProjectInitSpec(parent, "New", profile=ProjectProfile(word_min=-2))):
                with self.assertRaises(ValueError):
                    initialize_project(spec)
                self.assertEqual(list(parent.iterdir()), [])

    def test_existing_empty_nonempty_and_symlink_destinations_are_not_modified(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory)
            empty = parent / "Empty"
            empty.mkdir()
            full = parent / "Full"
            full.mkdir()
            (full / "main.tex").write_bytes(b"original")
            link = parent / "Link"
            link.symlink_to(empty, target_is_directory=True)
            for path in (empty, full, link):
                with self.subTest(path=path), self.assertRaises(FileExistsError):
                    initialize_project(ProjectInitSpec(parent, path.name))
            self.assertEqual(list(empty.iterdir()), [])
            self.assertEqual((full / "main.tex").read_bytes(), b"original")
            self.assertTrue(link.is_symlink())

    def test_partial_creation_failure_is_explicit_and_preserves_foreign_file(self):
        from app.core import project_tools
        with TemporaryDirectory() as directory:
            parent = Path(directory)
            original = project_tools._write_new_project_file
            def concurrent(path, root, payload):
                path.write_bytes(b"external winner")
                return original(path, root, payload)
            with patch.object(project_tools, "_write_new_project_file", side_effect=concurrent):
                with self.assertRaisesRegex(OSError, "未完成"):
                    initialize_project(ProjectInitSpec(parent, "New"))
            self.assertEqual((parent / "New" / "main.tex").read_bytes(), b"external winner")

    def test_sanitized_names_are_single_components_and_not_windows_devices(self):
        self.assertEqual(sanitize_project_name("中文 项目"), "中文 项目")
        for name in ("CON", "nul.tex", "LPT1", "COM3.log", "..", "a/b\\c", "bad\0name"):
            clean = sanitize_project_name(name)
            self.assertNotIn("/", clean)
            self.assertNotIn("\\", clean)
            self.assertNotIn("\0", clean)
            self.assertNotIn(clean.split(".")[0].upper(), {"CON", "NUL", "LPT1", "COM3"})

    def test_initialize_project_creates_main_assets_and_bib(self) -> None:
        with TemporaryDirectory() as directory:
            project = initialize_project(ProjectInitSpec(Path(directory), "Physics IA", "ib_ia_report"))

            self.assertTrue(project.tex_file.exists())
            self.assertTrue(project.bib_file.exists())
            self.assertTrue((project.root_dir / "figures").is_dir())
            self.assertTrue((project.root_dir / "tables").is_dir())
            self.assertIn(BIBLIOGRAPHY_LINE, project.tex_file.read_text(encoding="utf-8"))

    def test_sanitize_project_name(self) -> None:
        self.assertEqual(sanitize_project_name(" IA / Physics? "), "IA _ Physics")
        self.assertEqual(sanitize_project_name(""), "LaTeX_Project")

    def test_ensure_bibliography_is_idempotent(self) -> None:
        text = "\\documentclass{article}\n\\begin{document}\nHi\n\\end{document}\n"
        updated = ensure_bibliography(text)

        self.assertEqual(ensure_bibliography(updated), updated)
        self.assertIn("\\bibliographystyle{plain}", updated)

    def test_bib_entry_generation_and_append(self) -> None:
        entry = BibEntrySpec(
            entry_type="article",
            key="Storm2024",
            author="A. Storm",
            title="Weather",
            journal="Journal",
            year="2024",
        )

        snippet = bib_entry_snippet(entry)
        updated = append_bib_entry("", entry)

        self.assertIn("@article{Storm2024,", snippet)
        self.assertIn("author = {A. Storm}", snippet)
        self.assertEqual(bib_keys(updated), {"Storm2024"})

    def test_label_and_reference_scans(self) -> None:
        text = (
            "\\section{A}\\label{sec:intro}\n"
            "\\begin{figure}\\label{fig:plot}\\end{figure}\n"
            "\\ref{fig:plot} \\autoref{tab:data} \\label{fig:plot}\n"
        )

        labels = scan_labels(text)

        self.assertEqual(labels[0].kind, "章节")
        self.assertIn("fig:plot", duplicate_labels(text))
        self.assertEqual(undefined_references(text), {"tab:data"})
        self.assertEqual(reference_snippet("fig:plot", "autoref"), "\\autoref{fig:plot}")

    def test_citation_scans(self) -> None:
        tex = "\\cite{Storm2024, Missing}"
        bib = "@article{Storm2024,\n  title = {Weather}\n}"

        self.assertEqual(scan_citations(tex), {"Storm2024", "Missing"})
        self.assertEqual(undefined_citations(tex, bib), {"Missing"})
        self.assertEqual(citation_snippet("Storm2024"), "\\cite{Storm2024}")

    def test_bib_import_accepts_raw_bibtex(self) -> None:
        result = bib_import_from_text("@article{Storm2024,\n  title = {Weather}\n}")

        self.assertEqual(result.key, "Storm2024")
        self.assertEqual(result.source, "BibTeX")
        self.assertIn("@article{Storm2024", append_bib_import("", result))

    def test_bib_import_generates_doi_arxiv_url_and_title_entries(self) -> None:
        doi = bib_import_from_text("https://doi.org/10.1000/example")
        arxiv = bib_import_from_text("arXiv:2604.15366")
        url = bib_import_from_text("https://example.com/paper")
        title = bib_import_from_text("A useful paper title")

        self.assertEqual(doi.source, "DOI")
        self.assertIn("doi = {10.1000/example}", doi.bibtex)
        self.assertEqual(arxiv.source, "arXiv")
        self.assertIn("archivePrefix = {arXiv}", arxiv.bibtex)
        self.assertEqual(url.source, "URL")
        self.assertIn("@online{web_example_com", url.bibtex)
        self.assertEqual(title.source, "标题")
        self.assertIn("title = {A useful paper title}", title.bibtex)

    def test_fetch_bib_online_doi_returns_real_bibtex(self) -> None:
        requests = []
        opener = _fake_opener(b"@article{Real2024,\n  title = {Real Title}\n}", requests=requests)
        result = fetch_bib_online("10.1000/example", opener=opener)
        assert result is not None
        self.assertEqual(result.source, "DOI（在线）")
        self.assertEqual(result.key, "Real2024")
        self.assertIn("Real Title", result.bibtex)
        self.assertEqual(
            requests[0].full_url,
            "https://api.crossref.org/works/10.1000%2Fexample/transform/application/x-bibtex",
        )

    def test_fetch_bib_online_arxiv_parses_atom(self) -> None:
        atom = (
            '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            "<title>A  Great\nPaper</title>"
            "<published>2021-03-04T00:00:00Z</published>"
            "<author><name>Ada Lovelace</name></author>"
            "<author><name>Alan Turing</name></author>"
            "</entry></feed>"
        )
        result = fetch_bib_online("2604.15366", opener=_fake_opener(atom.encode("utf-8")))
        assert result is not None
        self.assertEqual(result.source, "arXiv（在线）")
        self.assertIn("title = {A Great Paper}", result.bibtex)
        self.assertIn("author = {Ada Lovelace and Alan Turing}", result.bibtex)
        self.assertIn("year = {2021}", result.bibtex)

    def test_fetch_bib_online_rejects_unexpected_final_host(self) -> None:
        opener = _fake_opener(b"@article{x, title={x}}", final_url="http://127.0.0.1/private")

        with self.assertRaisesRegex(OSError, "重定向"):
            fetch_bib_online("10.1000/example", opener=opener)

    def test_fetch_bib_online_rejects_oversized_response(self) -> None:
        opener = _fake_opener(b"x" * (1024 * 1024 + 1))

        with self.assertRaisesRegex(OSError, "过大"):
            fetch_bib_online("10.1000/example", opener=opener)

    def test_fetch_bib_online_rejects_dangerous_tex_metadata(self) -> None:
        opener = _fake_opener(b"@article{x, title={\\input{/tmp/secret}}}")

        with self.assertRaisesRegex(OSError, "不安全"):
            fetch_bib_online("10.1000/example", opener=opener)

    def test_fetch_bib_online_returns_none_for_plain_title(self) -> None:
        self.assertIsNone(fetch_bib_online("Just a title", opener=_fake_opener(b"")))

    def test_fetch_bib_online_raises_on_network_error(self) -> None:
        import urllib.error

        def opener(_request, timeout=None):  # noqa: ARG001
            raise urllib.error.URLError("no network")

        with self.assertRaises(OSError):
            fetch_bib_online("10.1000/example", opener=opener)

    def test_append_bib_import_rejects_duplicate_key(self) -> None:
        result = bib_import_from_text("@article{Storm2024,\n  title = {Weather}\n}")

        with self.assertRaises(ValueError):
            append_bib_import("@article{Storm2024,\n  title = {Old}\n}\n", result)


class _FakeResponse:
    def __init__(self, payload: bytes, *, final_url: str | None = None) -> None:
        self._payload = payload
        self._final_url = final_url
        self.headers = SimpleNamespace(get_content_charset=lambda: "utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]

    def geturl(self) -> str | None:
        return self._final_url


def _fake_opener(payload: bytes, *, requests=None, final_url: str | None = None):  # type: ignore[no-untyped-def]
    def opener(request, timeout=None):  # noqa: ARG001
        if requests is not None:
            requests.append(request)
        return _FakeResponse(payload, final_url=final_url or request.full_url)

    return opener
