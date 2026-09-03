"""Safe, project-scoped rename and move rules for the file toolbox.

The GUI deliberately uses a read-only ``QFileSystemModel``.  Mutations pass
through this module so path containment, collisions, symbolic links, and
LaTeX references are checked before the filesystem is touched.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Mapping

from app.core.image_assets import IMAGE_SUFFIXES
from app.core.paths import strip_latex_comments
from app.core.text_encoding import LatexTextDecodeError, decode_latex_bytes


PROJECT_FILE_SUFFIXES = frozenset({".tex", ".bib", *IMAGE_SUFFIXES})
PROJECT_FILE_FILTERS = (
    "*.tex",
    "*.TEX",
    "*.bib",
    "*.BIB",
    "*.png",
    "*.PNG",
    "*.jpg",
    "*.JPG",
    "*.jpeg",
    "*.JPEG",
    "*.pdf",
    "*.PDF",
    "*.eps",
    "*.EPS",
    "*.svg",
    "*.SVG",
)
PROTECTED_PROJECT_DIRS = frozenset({".icstex", ".latex_build"})
LATEX_REFERENCE_SOURCE_SUFFIXES = frozenset({".tex", ".sty", ".cls", ".ltx"})
MAX_REFERENCE_SCAN_FILES = 2_000

_REFERENCE_RE = re.compile(
    r"\\(?P<command>input|include|subfile|includegraphics|bibliography|addbibresource)"
    r"\s*(?:\[[^\]]*\]\s*)?\{(?P<target>[^{}]+)\}",
    re.IGNORECASE,
)
_GRAPHICS_PATH_RE = re.compile(r"\\graphicspath\s*\{(?P<paths>(?:\{[^{}]+\}\s*)+)\}")
_BRACED_PATH_RE = re.compile(r"\{([^{}]+)\}")
_MAGIC_ROOT_RE = re.compile(
    r"^\s*%\s*!\s*T[eE]X\s+root\s*=\s*(?P<target>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


class ProjectFileOperationError(ValueError):
    """The requested filesystem mutation cannot be proven safe."""


@dataclass(frozen=True)
class ProjectPathMove:
    project_root: Path
    source: Path
    destination: Path
    source_is_directory: bool


@dataclass(frozen=True)
class ProjectPathReference:
    owner: Path
    line: int
    command: str
    raw_target: str
    reason: str


def rename_destination(source: str | Path, new_name: str) -> Path:
    """Return a sibling destination after validating a single path component."""

    clean = new_name.strip()
    if not clean or clean in {".", ".."} or "/" in clean or "\\" in clean:
        raise ProjectFileOperationError("名称必须是单个非空文件名，不能包含路径分隔符。")
    return Path(source).expanduser().parent / clean


def plan_project_path_move(
    project_root: str | Path,
    source: str | Path,
    destination: str | Path,
) -> ProjectPathMove:
    """Validate a no-overwrite, same-filesystem move within one project root."""

    try:
        root = Path(project_root).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ProjectFileOperationError(f"项目目录不可用：{exc}") from exc
    if not root.is_dir():
        raise ProjectFileOperationError("项目根目录不是文件夹。")

    source_input = Path(source).expanduser()
    if source_input.is_symlink():
        raise ProjectFileOperationError("为避免路径越界，不能移动符号链接。")
    try:
        source_path = source_input.resolve(strict=True)
    except OSError as exc:
        raise ProjectFileOperationError(f"源路径不可用：{exc}") from exc
    if not source_path.is_relative_to(root):
        raise ProjectFileOperationError("源路径不在当前项目内。")
    if source_path == root:
        raise ProjectFileOperationError("不能从文件树中移动或重命名项目根目录。")

    destination_input = Path(destination).expanduser()
    if destination_input.exists() or destination_input.is_symlink():
        raise ProjectFileOperationError("目标位置已存在同名文件或文件夹。")
    try:
        destination_parent = destination_input.parent.resolve(strict=True)
    except OSError as exc:
        raise ProjectFileOperationError(f"目标目录不可用：{exc}") from exc
    if not destination_parent.is_dir():
        raise ProjectFileOperationError("目标位置的上级路径不是文件夹。")
    destination_path = destination_parent / destination_input.name
    if not destination_path.is_relative_to(root):
        raise ProjectFileOperationError("目标位置不在当前项目内。")
    if source_path == destination_path:
        raise ProjectFileOperationError("源路径与目标路径相同。")

    source_is_directory = source_path.is_dir()
    if source_is_directory and destination_path.is_relative_to(source_path):
        raise ProjectFileOperationError("不能把文件夹移动到它自己的内部。")
    if _contains_protected_component(root, source_path) or _contains_protected_component(
        root, destination_path
    ):
        raise ProjectFileOperationError("不能移动 ICSTeX 的内部预览或编译目录。")
    try:
        if source_path.stat().st_dev != destination_parent.stat().st_dev:
            raise ProjectFileOperationError("目标不在同一文件系统；为保证原子移动，本次操作已取消。")
    except OSError as exc:
        raise ProjectFileOperationError(f"无法检查文件系统：{exc}") from exc

    return ProjectPathMove(
        project_root=root,
        source=source_path,
        destination=destination_path,
        source_is_directory=source_is_directory,
    )


def find_move_blockers(
    plan: ProjectPathMove,
    *,
    text_overrides: Mapping[Path, str] | None = None,
) -> tuple[ProjectPathReference, ...]:
    """Find LaTeX references that would become invalid after ``plan``.

    References from outside a moved path into it always block the operation.
    Relative references originating inside a moved path block only when the
    same literal no longer resolves to the original target at the destination.
    Open editor buffers can be supplied as overrides so unsaved references are
    never ignored.
    """

    overrides = {
        Path(path).expanduser().resolve(): text
        for path, text in (text_overrides or {}).items()
    }
    tex_files = [
        path
        for path in plan.project_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in LATEX_REFERENCE_SOURCE_SUFFIXES
        and not path.is_symlink()
        and not any(part in PROTECTED_PROJECT_DIRS for part in path.parts)
    ]
    for path in overrides:
        if path.suffix.lower() in LATEX_REFERENCE_SOURCE_SUFFIXES:
            tex_files.append(path)
    tex_files = sorted(set(tex_files))
    if len(tex_files) > MAX_REFERENCE_SCAN_FILES:
        raise ProjectFileOperationError(
            f"项目包含超过 {MAX_REFERENCE_SCAN_FILES} 个 LaTeX 源文件，无法在界面中安全完成引用检查。"
        )

    blockers: list[ProjectPathReference] = []
    for owner in tex_files:
        text = overrides.get(owner)
        if text is None:
            try:
                text = decode_latex_bytes(owner.read_bytes()).text
            except LatexTextDecodeError as exc:
                raise ProjectFileOperationError(
                    f"无法按声明编码检查引用：{owner.name}（{exc.encoding}）。"
                ) from exc
            except OSError as exc:
                raise ProjectFileOperationError(f"无法读取引用来源：{owner}：{exc}") from exc
        blockers.extend(_blockers_in_text(plan, owner, text))
    return tuple(blockers)


def execute_project_path_move(plan: ProjectPathMove) -> None:
    """Execute a previously planned move without overwriting a destination."""

    current = plan_project_path_move(plan.project_root, plan.source, plan.destination)
    if current != plan:
        raise ProjectFileOperationError("文件状态在确认后发生变化；本次操作已取消。")
    if plan.destination.exists() or plan.destination.is_symlink():
        raise ProjectFileOperationError("目标位置刚刚出现同名项目；本次操作已取消。")
    try:
        os.rename(plan.source, plan.destination)
    except OSError as exc:
        raise ProjectFileOperationError(f"移动失败，原路径保持不变：{exc}") from exc


def remap_moved_path(path: str | Path, plan: ProjectPathMove) -> Path | None:
    """Map ``path`` to its location after ``plan``; return ``None`` if unaffected."""

    candidate = Path(path).expanduser().resolve()
    if candidate == plan.source:
        return plan.destination
    if plan.source_is_directory and candidate.is_relative_to(plan.source):
        return plan.destination / candidate.relative_to(plan.source)
    return None


def _blockers_in_text(
    plan: ProjectPathMove,
    owner: Path,
    text: str,
) -> list[ProjectPathReference]:
    clean_text = strip_latex_comments(text)
    owner_is_moved = remap_moved_path(owner, plan) is not None
    blockers: list[ProjectPathReference] = []
    references = [
        (match.group("command").lower(), match.group("target"), match.start())
        for match in _REFERENCE_RE.finditer(clean_text)
    ]
    references.extend(
        ("magic-root", match.group("target").strip(), match.start())
        for match in _MAGIC_ROOT_RE.finditer(text)
    )
    for command, raw_value, position in references:
        values = _reference_values(command, raw_value)
        for raw_target in values:
            old_targets = _reference_candidates(
                owner,
                plan.project_root,
                command,
                raw_target,
                clean_text,
                existing_only=True,
            )
            if not old_targets:
                if _dynamic_reference_may_target(raw_target, plan.source):
                    line_source = text if command == "magic-root" else clean_text
                    blockers.append(
                        ProjectPathReference(
                            owner=owner,
                            line=line_source.count("\n", 0, position) + 1,
                            command=command,
                            raw_target=raw_target,
                            reason="动态 LaTeX 引用无法被安全解析",
                        )
                    )
                continue
            line_source = text if command == "magic-root" else clean_text
            line = line_source.count("\n", 0, position) + 1
            if not owner_is_moved:
                if any(_path_is_moved(target, plan) for target in old_targets):
                    blockers.append(
                        ProjectPathReference(
                            owner=owner,
                            line=line,
                            command=command,
                            raw_target=raw_target,
                            reason="其他 LaTeX 文件仍引用该路径",
                        )
                    )
                continue

            moved_owner = remap_moved_path(owner, plan)
            assert moved_owner is not None
            for old_target in old_targets:
                if plan.source_is_directory and _path_is_moved(old_target, plan):
                    continue
                if Path(raw_target).expanduser().is_absolute():
                    continue
                new_targets = _reference_candidates(
                    moved_owner,
                    plan.project_root,
                    command,
                    raw_target,
                    clean_text,
                    existing_only=False,
                )
                if old_target not in new_targets:
                    blockers.append(
                        ProjectPathReference(
                            owner=owner,
                            line=line,
                            command=command,
                            raw_target=raw_target,
                            reason="移动后该文件中的相对引用会改变目标",
                        )
                    )
                    break
    return blockers


def _reference_values(command: str, raw: str) -> tuple[str, ...]:
    values = raw.split(",") if command == "bibliography" else [raw]
    return tuple(value.strip() for value in values if value.strip())


def _reference_candidates(
    owner: Path,
    project_root: Path,
    command: str,
    raw_target: str,
    text: str,
    *,
    existing_only: bool,
) -> tuple[Path, ...]:
    if any(token in raw_target for token in ("\\", "#", "{", "}")):
        return ()
    raw_path = Path(raw_target).expanduser()
    bases: list[Path]
    if raw_path.is_absolute():
        bases = [Path("/")]
    else:
        bases = [owner.parent, project_root]
        if command == "includegraphics":
            for match in _GRAPHICS_PATH_RE.finditer(text):
                for graphic_dir in _BRACED_PATH_RE.findall(match.group("paths")):
                    directory = Path(graphic_dir.strip())
                    if directory.is_absolute():
                        bases.append(directory)
                    else:
                        bases.extend((owner.parent / directory, project_root / directory))

    suffixes: tuple[str, ...]
    if raw_path.suffix:
        suffixes = ("",)
    elif command in {"input", "include", "subfile", "magic-root"}:
        suffixes = ("", ".tex")
    elif command in {"bibliography", "addbibresource"}:
        suffixes = ("", ".bib")
    elif command == "includegraphics":
        suffixes = ("", *sorted(IMAGE_SUFFIXES))
    else:
        suffixes = ("",)

    candidates: list[Path] = []
    for base in bases:
        candidate = raw_path if raw_path.is_absolute() else base / raw_path
        for suffix in suffixes:
            expanded = candidate.with_suffix(suffix) if suffix else candidate
            resolved = expanded.resolve(strict=False)
            if existing_only and not resolved.exists():
                continue
            if resolved not in candidates:
                candidates.append(resolved)
    return tuple(candidates)


def _path_is_moved(path: Path, plan: ProjectPathMove) -> bool:
    return path == plan.source or (
        plan.source_is_directory and path.is_relative_to(plan.source)
    )


def _contains_protected_component(root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return any(part in PROTECTED_PROJECT_DIRS for part in relative.parts)


def _dynamic_reference_may_target(raw_target: str, source: Path) -> bool:
    if not any(token in raw_target for token in ("\\", "#", "{", "}")):
        return False
    folded = raw_target.casefold().replace("\\", "/")
    for candidate in (source.name.casefold(), source.stem.casefold()):
        if folded.endswith(candidate) or f"/{candidate}" in folded:
            return True
    return False
