"""Explicit before/after/current journal decisions, recovered only to a new copy.

A write journal covers changed managed files, not a complete historical project.
Unaffected selected files come from the reviewed current disk. Nothing deletes or
repairs the pending evidence in the original project.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from itertools import islice
from pathlib import Path
import stat

from app.core.blocks.assembly import build_latex_files
from app.core.blocks.project_repository import project_payloads
from app.core.blocks.project_write import PENDING_PATH, MAX_BATCH_BYTES, _json
from app.core.project_checkpoint import (
    CheckpointInfo, FileEntry, MAX_FILES, MAX_DRAFTS, MAX_TOTAL_BYTES, MAX_MANIFEST_BYTES,
    _DIGEST, _DRAFT_SUFFIX, _cancel, _candidate_directory, _check_signature, _draft_entries,
    _json_bytes, _publish_restore, _read_file, _validate_paths, checkpoint_candidates,
)
from app.core.project_dependencies import MAX_SOURCE_BYTES, safe_project_input
from app.core.project_recovery import parse_saved_block_model

_OWNED = {".icstex/blocks.json", ".icstex/layouts.json", ".icstex/sources.json",
          "styles/document-theme.json", "main.tex", "styles/icstex-generated.sty"}


@dataclass(frozen=True)
class JournalEntry:
    path: str
    before: bytes | None
    after: bytes
    current: bytes | None

    @property
    def state(self):
        if self.current == self.before:
            return "before"
        if self.current == self.after:
            return "after"
        return "external"


@dataclass(frozen=True)
class JournalReview:
    project: Path
    entries: tuple[JournalEntry, ...]
    files: tuple[tuple[str, bytes | None], ...]
    evidence: tuple[tuple[str, bytes], ...]
    observations: tuple[tuple[str, tuple | None], ...]
    identity: tuple[int, int]
    warnings: tuple[str, ...]


def _optional(root, path, cancelled):
    try:
        return _read_file(root, path, cancelled)
    except FileNotFoundError:
        if safe_project_input(root, root / path, allow_internal=True) is None:
            raise OSError("恢复路径包含链接或越界；原件保留。")
        return None, None


def _journal_names(root):
    directory = root / PENDING_PATH
    with _candidate_directory(root, directory) as entries:
        names = []
        for entry in entries:
            if len(names) > 2 * MAX_FILES or not entry.is_file(follow_symlinks=False):
                raise ValueError("写入日志含未知目录、链接或超限对象；不自动清理。")
            names.append(entry.name)
        return frozenset(names)


def _sha(payload):
    return hashlib.sha256(payload).hexdigest() if payload is not None else None


def inspect_write_journal(project, *, paths=None, cancelled=None, expected=None):
    raw = Path(project).expanduser().absolute()
    if raw.is_symlink():
        raise ValueError("不能从项目目录链接恢复。")
    root = raw.resolve(strict=True)
    initial = root.lstat()
    if not stat.S_ISDIR(initial.st_mode):
        raise ValueError("请选择项目目录。")
    identity = (initial.st_dev, initial.st_ino)
    names = _journal_names(root)
    manifest, observation = _read_file(root, (PENDING_PATH / "manifest.json").as_posix(), cancelled)
    if len(manifest) > MAX_MANIFEST_BYTES:
        raise ValueError("写入日志清单超过上限。")
    value = _json(manifest)
    if (not isinstance(value, dict) or set(value) != {"format", "version", "state", "entries"}
            or value["format"] != "icstex-block-write" or type(value["version"]) is not int
            or value["version"] != 1 or value["state"] != "pending"
            or not isinstance(value["entries"], list) or not 1 <= len(value["entries"]) <= MAX_FILES):
        raise ValueError("未知或不完整的写入日志；原件保留，不自动迁移。")
    evidence = [("manifest.json", manifest)]
    observations = [((PENDING_PATH / "manifest.json").as_posix(), observation)]
    journal_paths, entries = [], []
    expected_names = {"manifest.json"}
    total = 0
    for index, item in enumerate(value["entries"]):
        if (not isinstance(item, dict) or set(item) != {"path", "index", "before", "after"}
                or type(item["index"]) is not int or item["index"] != index
                or not isinstance(item["path"], str)):
            raise ValueError("日志条目身份无效。")
        path = item["path"]
        _validate_paths([path])
        relative = Path(path)
        if path not in _OWNED and not (len(relative.parts) == 2 and relative.parts[0] == "blocks"
                                      and relative.suffix == ".tex"):
            raise ValueError("日志声称的目标不是受管 Block 文件。")
        journal_paths.append(path)
        versions = {}
        for side in ("before", "after"):
            digest = item[side]
            if digest is None and side == "before":
                versions[side] = None
                continue
            if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
                raise ValueError("日志摘要无效。")
            name = f"{side}-{index}.bin"
            expected_names.add(name)
            payload, observed = _read_file(root, (PENDING_PATH / name).as_posix(), cancelled)
            total += len(payload)
            if len(payload) > MAX_SOURCE_BYTES or total > MAX_BATCH_BYTES:
                raise ValueError("写入前后证据超过单文件或合计上限。")
            if _sha(payload) != digest:
                raise ValueError("写入日志内容摘要不符；不发布恢复项目。")
            evidence.append((name, payload))
            observations.append(((PENDING_PATH / name).as_posix(), observed))
            versions[side] = payload
        current, observed = _optional(root, path, cancelled)
        observations.append((path, observed))
        entries.append(JournalEntry(path, versions["before"], versions["after"], current))
    _validate_paths(journal_paths)
    if names != expected_names:
        raise ValueError("日志缺少对象或含未识别残留；不自动清理或恢复。")
    warnings = ()
    if paths is None:
        paths, warnings = checkpoint_candidates(root, cancelled=cancelled)
    paths = tuple(islice(paths, MAX_FILES + 1))
    if len(paths) > MAX_FILES:
        raise ValueError("恢复文件选择超过上限。")
    paths = tuple(sorted(set(paths) | set(journal_paths)))
    if len(paths) > MAX_FILES:
        raise ValueError("恢复文件选择超过上限。")
    _validate_paths(paths)
    changed = {entry.path: entry for entry in entries}
    files = []
    for path in paths:
        if path in changed:
            payload = changed[path].current
        else:
            payload, observed = _read_file(root, path, cancelled)
            observations.append((path, observed))
        total += len(payload or b"")
        if total > MAX_TOTAL_BYTES:
            raise ValueError("当前文件与日志证据合计超过 256 MiB。")
        files.append((path, payload))
    # Re-read the exact selected input set. Absence is checked too; additions at
    # a formerly absent transaction target invalidate the reviewed selection.
    first = {**dict(files), **{(PENDING_PATH / name).as_posix(): payload for name, payload in evidence}}
    for path, observed in observations:
        again, current_observation = _optional(root, path, cancelled)
        if again != first[path] or current_observation != observed:
            raise OSError("恢复输入在读取时变化；请重新审阅。")
    for path, observed in observations:
        _cancel(cancelled)
        if observed is None:
            if _optional(root, path, cancelled) != (None, None):
                raise OSError("原先不存在的恢复目标已出现。")
        else:
            _check_signature(root, path, observed)
    current = root.lstat()
    if (not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != identity
            or _journal_names(root) != names):
        raise OSError("恢复项目或日志目录在读取时变化。")
    review = JournalReview(root, tuple(entries), tuple(files), tuple(evidence), tuple(observations), identity, warnings)
    if expected is not None and (review.project != expected.project or review.identity != expected.identity
            or review.entries != expected.entries or review.files != expected.files
            or review.evidence != expected.evidence or review.observations != expected.observations):
        raise OSError("写入日志或项目在审阅后变化；没有发布恢复项目。")
    return review


def journal_candidate(review, choices, selected=None):
    """An explicit choice for EVERY changed file; no conflict winner is inferred."""
    targets = {entry.path for entry in review.entries}
    if set(choices) != targets or any(value not in {"before", "after", "current"} for value in choices.values()):
        raise ValueError("请逐项选择全部写入目标的版本；没有默认冲突胜出方。")
    files = dict(review.files)
    selected = set(files) if selected is None else set(selected)
    if not targets <= selected or not selected <= files.keys():
        raise ValueError("全部日志目标必须参与审阅；只能选择已核验的项目文件。")
    for entry in review.entries:
        files[entry.path] = getattr(entry, choices[entry.path])
    result = {path: payload for path, payload in files.items() if path in selected and payload is not None}
    # A byte-preserved copy is not necessarily an editable, coherent Block model.
    # Refuse combinations that cannot be loaded and rendered without rewriting.
    model = parse_saved_block_model(result)
    project_payloads(review.project, **model)
    arguments = {key: model[key] for key in ("registry", "layout", "document_theme")}
    generated = build_latex_files(review.project, **arguments)
    trusted = build_latex_files(review.project, **arguments, allow_trusted_raw_latex=True)
    for path, text in generated.items():
        relative = path.relative_to(review.project).as_posix()
        if result.get(relative) not in (text.encode(), trusted[path].encode()):
            raise ValueError(f"所选模型与生成源码不一致：{relative}；请比较其他版本，原件保留。")
    return result


def recover_write_journal(review, choices, target, *, selected=None, drafts=(), cancelled=None):
    """Publish a reviewed candidate, retaining all changed-file alternatives."""
    _cancel(cancelled)
    fresh = inspect_write_journal(review.project, paths=[p for p, _ in review.files],
                                  cancelled=cancelled, expected=review)
    destination = Path(target).expanduser().absolute()
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.is_relative_to(fresh.project):
        raise ValueError("请选择原项目之外的新恢复目录；不会在原项目内写入。")
    choices = dict(choices)
    files = journal_candidate(fresh, choices, selected)
    drafts = tuple(islice(drafts, MAX_DRAFTS + 1))
    if len(drafts) > MAX_DRAFTS:
        raise ValueError("恢复草稿超过上限。")
    draft_entries = _draft_entries(drafts)
    info = CheckpointInfo(datetime.now(timezone.utc).isoformat(),
        tuple(FileEntry(path, _sha(payload), len(payload)) for path, payload in sorted(files.items())), draft_entries)
    report = {"format": "icstex-reviewed-write-recovery", "version": 1,
        "scope": "Selected current files plus explicit journal choices; not a complete historical snapshot",
        "original_pending_evidence": "preserved; never removed or unlocked",
        "block_validation": "known metadata and matching managed generation; not a successful FINAL build",
        "entries": [{"path": entry.path, "choice": choices[entry.path], "current_state": entry.state,
                     "before": _sha(entry.before), "after": _sha(entry.after), "current": _sha(entry.current),
                     "current_object": f"current-{i}.bin" if entry.current is not None else None}
                    for i, entry in enumerate(fresh.entries)],
        "files": [{"path": e.path, "sha256": e.sha256, "size": e.size} for e in info.files]}
    payloads = [("project/" + path, payload) for path, payload in files.items()]
    payloads += [("drafts/" + draft.id + _DRAFT_SUFFIX[draft.kind], draft.payload) for draft in drafts]
    payloads += [("recovery-evidence/journal/" + name, payload) for name, payload in fresh.evidence]
    payloads += [(f"recovery-evidence/current-{i}.bin", entry.current) for i, entry in enumerate(fresh.entries)
                 if entry.current is not None]
    payloads.append(("recovery-evidence/decision.json", _json_bytes(report)))
    if len(info.manifest()) > MAX_MANIFEST_BYTES or sum(len(p) for _, p in payloads) > MAX_TOTAL_BYTES:
        raise ValueError("恢复结果和独立证据超过上限。")
    def recheck():
        inspect_write_journal(fresh.project, paths=[p for p, _ in fresh.files], cancelled=cancelled, expected=fresh)
    return _publish_restore(info, target, payloads, cancelled=cancelled, check_source=recheck)
