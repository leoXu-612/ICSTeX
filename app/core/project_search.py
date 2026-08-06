from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.search import SearchOptions, find_matches


SEARCH_SUFFIXES = {".tex", ".bib"}
IGNORED_DIRS = {".latex_build", ".icstex", "__pycache__"}
MAX_RESULTS = 500


@dataclass(frozen=True)
class ProjectSearchResult:
    file: Path
    line: int
    column: int
    excerpt: str


def search_project(
    project_dir: Path,
    query: str,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
    max_results: int = MAX_RESULTS,
) -> list[ProjectSearchResult]:
    if not query:
        return []
    root = project_dir.expanduser().resolve()
    options = SearchOptions(case_sensitive=case_sensitive, whole_word=whole_word)
    results: list[ProjectSearchResult] = []
    for path in _iter_search_files(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            for match in find_matches(line, query, options):
                results.append(
                    ProjectSearchResult(
                        file=path,
                        line=line_number,
                        column=match.start + 1,
                        excerpt=line.strip(),
                    )
                )
                if len(results) >= max_results:
                    return results
    return results


def _iter_search_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in SEARCH_SUFFIXES:
            files.append(path)
    return sorted(files)
