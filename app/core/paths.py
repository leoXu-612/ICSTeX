from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from app.core.magic_comments import magic_root_for


ROOT_CANDIDATES = ("main.tex", "root.tex", "document.tex", "paper.tex", "thesis.tex")
_INCLUDE_RE = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")


@dataclass(frozen=True)
class RootResolution:
    root: Path | None
    source: str

    @property
    def source_label(self) -> str:
        return {
            "current": "current file",
            "magic": "magic comment",
            "inferred": "inferred input/include",
            "unknown": "unknown",
        }.get(self.source, self.source)


def normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def is_latex_root(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() != ".tex":
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "\\documentclass" in text or "\\begin{document}" in text


def included_tex_files(path: str | Path) -> tuple[Path, ...]:
    source = normalize_path(path)
    try:
        text = source.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ()

    return included_tex_files_from_text(source, text)


def included_tex_files_from_text(path: str | Path, text: str) -> tuple[Path, ...]:
    """Resolve direct TeX dependencies from an in-memory source buffer."""
    positioned = included_tex_files_with_positions_from_text(path, text)
    return tuple(dict.fromkeys(included for included, _position in positioned))


def included_tex_files_with_positions_from_text(
    path: str | Path,
    text: str,
) -> tuple[tuple[Path, int], ...]:
    """Resolve direct dependencies and positions in comment-free source."""
    source = normalize_path(path)

    files: list[tuple[Path, int]] = []
    for match in _INCLUDE_RE.finditer(strip_latex_comments(text)):
        included = resolve_included_tex_path(source, match.group(1))
        if included is None:
            continue
        files.append((included, match.start()))
    return tuple(files)


def resolve_included_tex_path(source_path: str | Path, raw: str) -> Path | None:
    source = normalize_path(source_path)
    raw_path = raw.strip()
    if not raw_path:
        return None
    included = Path(raw_path).expanduser()
    if not included.is_absolute():
        included = source.parent / included
    if included.suffix == "":
        included = included.with_suffix(".tex")
    if included.suffix.lower() != ".tex":
        return None
    return included.resolve()


def latex_dependency_closure(root: str | Path, max_files: int = 200) -> frozenset[Path]:
    """Recursive \\input/\\include/\\subfile closure of a root, root included."""
    seen: set[Path] = set()
    queue = [normalize_path(root)]
    while queue and len(seen) < max_files:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(child for child in included_tex_files(current) if child not in seen)
    return frozenset(seen)


def find_root_tex(path: str | Path) -> Path | None:
    return resolve_root_tex(path).root


def resolve_root_tex(path: str | Path, *, selected_scope: str | Path | None = None) -> RootResolution:
    target = normalize_path(path)
    scope = normalize_path(selected_scope) if selected_scope is not None else None
    if target.is_file():
        magic_root = magic_root_for(target)
        if magic_root and _safe_single_file_magic_root(target, magic_root, selected_scope=scope):
            return RootResolution(magic_root, "magic")
        parent_root = _find_parent_root_for_child(target)
        if parent_root and (scope is None or parent_root.is_relative_to(scope)):
            return RootResolution(parent_root, "inferred")
        return RootResolution(target, "current") if target.suffix.lower() == ".tex" else RootResolution(None, "unknown")
    if not target.is_dir():
        return RootResolution(None, "unknown")

    tex_files = sorted(target.rglob("*.tex"))
    if not tex_files:
        return RootResolution(None, "unknown")

    by_name = {file.name.lower(): file for file in tex_files}
    for name in ROOT_CANDIDATES:
        candidate = by_name.get(name)
        if candidate and is_latex_root(candidate):
            return RootResolution(candidate, "current")

    for file in tex_files:
        magic_root = magic_root_for(file)
        if magic_root and magic_root.is_relative_to(target):
            return RootResolution(magic_root, "magic")

    roots = sorted(
        (file for file in tex_files if is_latex_root(file)),
        key=lambda file: _root_score(file),
        reverse=True,
    )
    if roots:
        source = "inferred" if included_tex_files(roots[0]) else "current"
        return RootResolution(roots[0], source)
    return RootResolution(tex_files[0], "unknown")


def _safe_single_file_magic_root(
    source: Path,
    candidate: Path,
    *,
    selected_scope: Path | None = None,
) -> bool:
    """Accept a parent project root only when it actually owns the child."""

    source = source.resolve()
    candidate = candidate.resolve()
    if not candidate.is_file() or candidate.is_symlink() or candidate.suffix.lower() != ".tex":
        return False
    if selected_scope is not None and (
        not source.is_relative_to(selected_scope) or not candidate.is_relative_to(selected_scope)
    ):
        return False
    if not source.is_relative_to(candidate.parent):
        return False
    return source in latex_dependency_closure(candidate)


def project_dir_for(root_file: str | Path) -> Path:
    return normalize_path(root_file).parent


def build_dir_for(root_file: str | Path) -> Path:
    return project_dir_for(root_file) / ".latex_build"


def preview_root_dir_for(root_file: str | Path) -> Path:
    root = normalize_path(root_file)
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", root.stem).strip("._") or "document"
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    return root.parent / ".icstex" / "preview" / f"{safe_stem}-{digest}"


def preview_build_dir_for(root_file: str | Path) -> Path:
    return preview_root_dir_for(root_file) / "build"


def preview_assets_dir_for(root_file: str | Path) -> Path:
    return preview_root_dir_for(root_file) / "assets"


def built_pdf_for(root_file: str | Path, output_dir: str | Path | None = None) -> Path:
    root = normalize_path(root_file)
    directory = normalize_path(output_dir) if output_dir else build_dir_for(root)
    return directory / f"{root.stem}.pdf"


def built_log_for(root_file: str | Path, output_dir: str | Path | None = None) -> Path:
    root = normalize_path(root_file)
    directory = normalize_path(output_dir) if output_dir else build_dir_for(root)
    return directory / f"{root.stem}.log"


def _find_parent_root_for_child(child: Path) -> Path | None:
    if child.suffix.lower() != ".tex":
        return None
    roots: list[Path] = []
    search_dirs = [child.parent, *child.parent.parents]
    for directory in search_dirs[:4]:
        try:
            tex_files = sorted(directory.glob("*.tex"))
        except OSError:
            continue
        for candidate in tex_files:
            if candidate.resolve() == child:
                continue
            if not is_latex_root(candidate):
                continue
            if child.resolve() in included_tex_files(candidate):
                roots.append(candidate.resolve())
    if not roots:
        return None
    return sorted(roots, key=lambda file: _root_score(file), reverse=True)[0]


def _root_score(path: Path) -> tuple[int, int, int, str]:
    name_score = len(ROOT_CANDIDATES) - ROOT_CANDIDATES.index(path.name.lower()) if path.name.lower() in ROOT_CANDIDATES else 0
    include_count = len(included_tex_files(path))
    return (include_count, name_score, -len(path.parts), str(path))


def strip_latex_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        lines.append(_strip_line_comment(line))
    return "\n".join(lines)


def _strip_line_comment(line: str) -> str:
    escaped = False
    for index, char in enumerate(line):
        if char == "\\":
            escaped = not escaped
            continue
        if char == "%" and not escaped:
            return line[:index]
        escaped = False
    return line
