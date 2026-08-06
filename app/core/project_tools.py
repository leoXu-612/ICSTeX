from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse
from xml.etree import ElementTree

from app.core.latex_insertions import template_for_key
from app.core.text_encoding import write_latex_text_atomic


PROJECT_FOLDERS = ("figures", "tables", "bib")
BIBLIOGRAPHY_LINE = "\\bibliography{bib/references}"
BIBLIOGRAPHY_STYLE_LINE = "\\bibliographystyle{plain}"
BEGIN_DOCUMENT = "\\begin{document}"
END_DOCUMENT = "\\end{document}"

LABEL_RE = re.compile(r"\\label\{([^{}]+)\}")
REF_RE = re.compile(r"\\(?:ref|autoref|eqref)\{([^{}]+)\}")
CITE_RE = re.compile(r"\\(?:cite|citep|citet|parencite|textcite)\{([^{}]+)\}")
BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)")
BIB_ENTRY_RE = re.compile(r"@(?P<type>\w+)\s*\{\s*(?P<key>[^,\s]+)\s*,", re.S)
DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s{}]+)", re.I)
ARXIV_RE = re.compile(r"(?:arxiv\s*:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?)", re.I)
URL_RE = re.compile(r"https?://[^\s{}]+", re.I)


@dataclass(frozen=True)
class ProjectInitSpec:
    parent_dir: Path
    project_name: str
    template_key: str = "ib_ia_report"


@dataclass(frozen=True)
class InitializedProject:
    root_dir: Path
    tex_file: Path
    bib_file: Path
    folders: tuple[Path, ...]


@dataclass(frozen=True)
class BibEntrySpec:
    entry_type: str
    key: str
    title: str = ""
    author: str = ""
    year: str = ""
    journal: str = ""
    publisher: str = ""
    url: str = ""


@dataclass(frozen=True)
class BibImportResult:
    key: str
    bibtex: str
    source: str


@dataclass(frozen=True)
class LabelInfo:
    name: str
    kind: str
    line: int


def sanitize_project_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name.strip()).strip(" ._")
    return cleaned or "LaTeX_Project"


def initialize_project(spec: ProjectInitSpec) -> InitializedProject:
    project_name = sanitize_project_name(spec.project_name)
    root = spec.parent_dir.expanduser().resolve() / project_name
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"项目文件夹不是空的：{root}")

    root.mkdir(parents=True, exist_ok=True)
    folders = tuple(root / folder for folder in PROJECT_FOLDERS)
    for folder in folders:
        folder.mkdir(exist_ok=True)

    template = template_for_key(spec.template_key)
    tex_file = root / "main.tex"
    bib_file = root / "bib" / "references.bib"
    write_latex_text_atomic(tex_file, ensure_bibliography(template.text), encoding="utf-8")
    if not bib_file.exists():
        write_latex_text_atomic(bib_file, "% 在这里添加 BibTeX 条目。\n", encoding="utf-8")
    return InitializedProject(root_dir=root, tex_file=tex_file, bib_file=bib_file, folders=folders)


def ensure_bibliography(text: str) -> str:
    if BIBLIOGRAPHY_LINE in text:
        return text
    block = f"\n{BIBLIOGRAPHY_STYLE_LINE}\n{BIBLIOGRAPHY_LINE}\n"
    if END_DOCUMENT in text:
        return text.replace(END_DOCUMENT, block + "\n" + END_DOCUMENT, 1)
    return text.rstrip() + block


def bib_entry_snippet(spec: BibEntrySpec) -> str:
    entry_type = spec.entry_type.strip().lower() or "misc"
    key = sanitize_bib_key(spec.key or spec.title or "source")
    fields = _bib_fields(spec)
    lines = [f"@{entry_type}{{{key},"]
    lines.extend(f"  {name} = {{{value}}}," for name, value in fields)
    if len(lines) > 1:
        lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return "\n".join(lines)


def append_bib_entry(bib_text: str, spec: BibEntrySpec) -> str:
    key = sanitize_bib_key(spec.key or spec.title or "source")
    if key in bib_keys(bib_text):
        raise ValueError(f"Bib key 已存在：{key}")
    suffix = "\n\n" if bib_text.strip() else ""
    return bib_text.rstrip() + suffix + bib_entry_snippet(replace(spec, key=key)) + "\n"


def bib_import_from_text(raw_text: str) -> BibImportResult:
    text = raw_text.strip()
    if not text:
        raise ValueError("请粘贴 BibTeX、DOI、arXiv ID、URL 或标题。")
    if text.startswith("@"):
        return _bib_import_from_raw_bibtex(text)

    doi_match = DOI_RE.search(text)
    if doi_match:
        doi = doi_match.group(1).rstrip(".,;")
        key = sanitize_bib_key(f"doi_{doi.split('/')[-1]}")
        return BibImportResult(
            key=key,
            source="DOI",
            bibtex=_bibtex_from_fields(
                "misc",
                key,
                (
                    ("title", f"Source for DOI {doi}"),
                    ("doi", doi),
                    ("url", f"https://doi.org/{doi}"),
                ),
            ),
        )

    arxiv_match = ARXIV_RE.search(text)
    if arxiv_match:
        identifier = arxiv_match.group(1)
        key = sanitize_bib_key(f"arxiv_{identifier}")
        return BibImportResult(
            key=key,
            source="arXiv",
            bibtex=_bibtex_from_fields(
                "misc",
                key,
                (
                    ("title", f"arXiv preprint {identifier}"),
                    ("eprint", identifier),
                    ("archivePrefix", "arXiv"),
                    ("url", f"https://arxiv.org/abs/{identifier}"),
                ),
            ),
        )

    url_match = URL_RE.search(text)
    if url_match:
        url = url_match.group(0).rstrip(".,;")
        key = sanitize_bib_key(f"web_{urlparse(url).netloc or 'source'}")
        return BibImportResult(
            key=key,
            source="URL",
            bibtex=_bibtex_from_fields("online", key, (("title", url), ("url", url))),
        )

    key = sanitize_bib_key(text[:48])
    return BibImportResult(
        key=key,
        source="标题",
        bibtex=_bibtex_from_fields("misc", key, (("title", text),)),
    )


def fetch_bib_online(raw_text: str, *, opener=urllib.request.urlopen, timeout: float = 10.0):  # type: ignore[no-untyped-def]
    """User-triggered online metadata fetch for a DOI or arXiv id.

    Returns a BibImportResult with real metadata, or None if the input is not a
    recognizable DOI/arXiv id (caller should fall back to the offline skeleton).
    Network/parse failures raise OSError so the caller can surface them.

    Privacy: only the identifier the user typed is sent. DOI uses Crossref
    content negotiation (returns ready-made BibTeX); arXiv uses its public API.
    ponytail: no third-party http/bibtex lib — stdlib urllib + ElementTree cover it.
    """
    text = raw_text.strip()
    if text.startswith("@"):
        return None

    doi_match = DOI_RE.search(text)
    if doi_match:
        doi = doi_match.group(1).rstrip(".,;")
        bibtex = _http_get(opener, f"https://doi.org/{doi}", {"Accept": "application/x-bibtex"}, timeout)
        result = _bib_import_from_raw_bibtex(bibtex)
        return replace(result, source="DOI（在线）")

    arxiv_match = ARXIV_RE.search(text)
    if arxiv_match:
        identifier = arxiv_match.group(1)
        atom = _http_get(opener, f"http://export.arxiv.org/api/query?id_list={identifier}", {}, timeout)
        return _arxiv_result_from_atom(identifier, atom)

    return None


def _http_get(opener, url: str, headers: dict[str, str], timeout: float) -> str:  # type: ignore[no-untyped-def]
    request = urllib.request.Request(url, headers={"User-Agent": "ICSTeX", **headers})
    try:
        with opener(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.URLError as exc:
        raise OSError(f"联网获取失败：{exc.reason}") from exc


def _arxiv_result_from_atom(identifier: str, atom: str):  # type: ignore[no-untyped-def]
    ns = {"a": "http://www.w3.org/2005/Atom"}
    try:
        entry = ElementTree.fromstring(atom).find("a:entry", ns)
    except ElementTree.ParseError as exc:
        raise OSError(f"arXiv 返回内容无法解析：{exc}") from exc
    if entry is None:
        raise OSError(f"arXiv 没有返回 {identifier} 的元数据。")
    title = re.sub(r"\s+", " ", (entry.findtext("a:title", default="", namespaces=ns) or "")).strip()
    authors = [
        (author.findtext("a:name", default="", namespaces=ns) or "").strip()
        for author in entry.findall("a:author", ns)
    ]
    author = " and ".join(name for name in authors if name)
    year = (entry.findtext("a:published", default="", namespaces=ns) or "")[:4]
    key = sanitize_bib_key(f"arxiv_{identifier}")
    return BibImportResult(
        key=key,
        source="arXiv（在线）",
        bibtex=_bibtex_from_fields(
            "misc",
            key,
            (
                ("title", title),
                ("author", author),
                ("year", year),
                ("eprint", identifier),
                ("archivePrefix", "arXiv"),
                ("url", f"https://arxiv.org/abs/{identifier}"),
            ),
        ),
    )


def append_bib_import(bib_text: str, result: BibImportResult) -> str:
    if result.key in bib_keys(bib_text):
        raise ValueError(f"Bib key 已存在：{result.key}")
    suffix = "\n\n" if bib_text.strip() else ""
    return bib_text.rstrip() + suffix + result.bibtex.rstrip() + "\n"


def bib_keys(bib_text: str) -> set[str]:
    return {match.group(1).strip() for match in BIB_KEY_RE.finditer(bib_text)}


def sanitize_bib_key(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9:_-]+", "_", value.strip()).strip("_:-")
    return cleaned or "source"


def _bib_import_from_raw_bibtex(text: str) -> BibImportResult:
    match = BIB_ENTRY_RE.search(text)
    if match is None:
        raise ValueError("没有识别到有效的 BibTeX key。请确认内容以 @article{key, ...} 形式开头。")
    key = sanitize_bib_key(match.group("key"))
    normalized = text.rstrip()
    if key != match.group("key"):
        normalized = normalized[: match.start("key")] + key + normalized[match.end("key") :]
    return BibImportResult(key=key, bibtex=normalized, source="BibTeX")


def _bibtex_from_fields(entry_type: str, key: str, fields: tuple[tuple[str, str], ...]) -> str:
    lines = [f"@{entry_type}{{{key},"]
    clean_fields = [(name, value.strip()) for name, value in fields if value.strip()]
    lines.extend(f"  {name} = {{{value}}}," for name, value in clean_fields)
    if len(lines) > 1:
        lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return "\n".join(lines)


def scan_labels(text: str) -> list[LabelInfo]:
    labels: list[LabelInfo] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in LABEL_RE.finditer(line):
            name = match.group(1)
            labels.append(LabelInfo(name=name, kind=label_kind(name), line=line_number))
    return labels


def scan_references(text: str) -> set[str]:
    refs: set[str] = set()
    for match in REF_RE.finditer(text):
        refs.add(match.group(1))
    return refs


def scan_citations(text: str) -> set[str]:
    citations: set[str] = set()
    for match in CITE_RE.finditer(text):
        citations.update(key.strip() for key in match.group(1).split(",") if key.strip())
    return citations


def duplicate_labels(text: str) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for label in scan_labels(text):
        if label.name in seen:
            duplicates.add(label.name)
        seen.add(label.name)
    return duplicates


def undefined_references(text: str) -> set[str]:
    defined = {label.name for label in scan_labels(text)}
    return scan_references(text) - defined


def undefined_citations(tex_text: str, bib_text: str) -> set[str]:
    return scan_citations(tex_text) - bib_keys(bib_text)


def reference_snippet(label: str, command: str = "ref") -> str:
    safe_command = command if command in {"ref", "autoref", "eqref"} else "ref"
    return f"\\{safe_command}{{{label}}}"


def citation_snippet(key: str) -> str:
    return f"\\cite{{{key}}}"


def label_kind(label: str) -> str:
    prefix = label.split(":", 1)[0].lower()
    return {
        "fig": "图片",
        "tab": "表格",
        "eq": "公式",
        "sec": "章节",
        "subsec": "章节",
        "app": "附录",
    }.get(prefix, "标签")


def _bib_fields(spec: BibEntrySpec) -> list[tuple[str, str]]:
    fields = [
        ("author", spec.author),
        ("title", spec.title),
        ("journal", spec.journal),
        ("publisher", spec.publisher),
        ("year", spec.year),
        ("url", spec.url),
    ]
    return [(name, value.strip()) for name, value in fields if value.strip()]
