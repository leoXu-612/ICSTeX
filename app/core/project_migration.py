"""Review selected local bytes and publish only an explicit new project copy.

Ordinary/current Block projects are copied byte-for-byte. Only the known legacy
envelope is converted. Every selected original is retained separately for legacy
conversion; unknown inputs never authorize a destructive write.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
from itertools import islice
from pathlib import Path
import stat

from app.core.blocks.assembly import build_latex_files
from app.core.blocks.migration import convert_legacy_document
from app.core.blocks.project_repository import project_payloads
from app.core.blocks.project_write import PENDING_PATH, _json
from app.core.project_checkpoint import (
    CheckpointInfo, FileEntry, MAX_FILES, MAX_DRAFTS, MAX_TOTAL_BYTES, MAX_MANIFEST_BYTES, MAX_FILE_BYTES,
    _DIGEST, _DRAFT_SUFFIX, _cancel, _check_signature, _draft_entries, _json_bytes, _relative,
    _publish_restore, _read_file, _validate_paths, checkpoint_candidates,
)
from app.core.project_dependencies import safe_project_input
from app.core.project_recovery import (RecoveryCopy, check_recovery_identity, read_recovery_copy,
    parse_block_model, parse_saved_block_model)

_BLOCKS = ".icstex/blocks.json"
_SIDE_METADATA = {".icstex/layouts.json", ".icstex/sources.json", "styles/document-theme.json"}
_COPY_SCOPE = "Explicit selected local files only; not all dependencies or cloud availability"
_ORIGINAL_POLICY = "unchanged; no move, in-place write, switch or compilation"


@dataclass(frozen=True)
class MigrationReview:
    project: Path
    kind: str
    original: tuple[tuple[str, bytes], ...]
    candidate: tuple[tuple[str, bytes], ...]
    observations: tuple[tuple[str, tuple], ...]
    identity: tuple[int, int]
    unmapped_keys: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def replaced(self):
        originals = dict(self.original)
        return tuple(path for path, payload in self.candidate
                     if path in originals and originals[path] != payload)


def _sha(payload):
    return hashlib.sha256(payload).hexdigest()


def _project_markers(root):
    """Absence matters too: a new metadata/journal file invalidates a review."""
    markers = {}
    for relative in (_BLOCKS, PENDING_PATH.as_posix(), *_SIDE_METADATA):
        path = root / relative
        if safe_project_input(root, path, allow_internal=True) is None:
            # Pending is a directory, handled with the same no-link boundary.
            if relative == PENDING_PATH.as_posix() and path.is_dir() and not path.is_symlink():
                raise ValueError("项目含中断写入日志；请先使用日志审阅恢复，不能绕过写入保护。")
            raise ValueError("项目元数据路径不可读、越界或包含链接。")
        try:
            path.lstat()
        except FileNotFoundError:
            markers[relative] = False
        else:
            if relative == PENDING_PATH.as_posix():
                raise ValueError("项目含中断写入日志；请先审阅恢复，不自动清理。")
            markers[relative] = True
    return markers


def _candidate(root, files):
    if _BLOCKS not in files:
        return "source-copy", files.copy(), ()
    raw = files[_BLOCKS]
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("Block 元数据超过 4 MiB。")
    envelope = _json(raw)
    if not isinstance(envelope, dict):
        raise ValueError("未知 Block 元数据格式。")
    if envelope.get("format") == "icstex-legacy-project":
        if _SIDE_METADATA & files.keys():
            raise ValueError("旧格式同时包含独立新元数据；归属不明确，保留原件，不自动合并。")
        conversion = convert_legacy_document(raw)
        model = parse_block_model(conversion.model)
        kind, unmapped = "legacy-conversion", conversion.unmapped_keys
    elif envelope.get("format") == "icstex-blocks":
        model = parse_saved_block_model(files)
        kind, unmapped = "block-copy", ()
    else:
        raise ValueError("未知或更新的项目格式；不自动迁移。")
    # Do not publish a seemingly complete converted project without its images.
    # Sources can be clipboard records; explicit unknown availability stays visible.
    for block in model["registry"].blocks():
        if block.type == "image" and block.content["source"] not in files:
            raise ValueError("所选文件缺少 Block 图片：" + block.content["source"])
    metadata = project_payloads(root, **model)
    args = {key: model[key] for key in ("registry", "layout", "document_theme")}
    generated = build_latex_files(root, **args)
    if kind == "block-copy":
        trusted = build_latex_files(root, **args, allow_trusted_raw_latex=True)
        for path, text in generated.items():
            if files.get(path.relative_to(root).as_posix()) not in (text.encode(), trusted[path].encode()):
                raise ValueError("现有 Block 模型与受管源码不一致；先审阅冲突，不自动覆盖。")
        return kind, files.copy(), unmapped
    result = files.copy()
    result.update({p.relative_to(root).as_posix(): b for p, b in metadata.items()})
    result.update({p.relative_to(root).as_posix(): s.encode() for p, s in generated.items()})
    # Reparse the exact output bytes, not only the intermediate model.
    parse_saved_block_model(result)
    return kind, result, unmapped


def inspect_project_migration(project, *, paths=None, cancelled=None, expected=None):
    """Two byte passes and identity checks; no original/destination writes."""
    raw = Path(project).expanduser().absolute()
    if raw.is_symlink():
        raise ValueError("请选择实际项目目录，不使用目录链接。")
    root = raw.resolve(strict=True)
    initial = root.lstat()
    if not stat.S_ISDIR(initial.st_mode):
        raise ValueError("请选择项目目录。")
    identity = (initial.st_dev, initial.st_ino)
    markers = _project_markers(root)
    warnings = ()
    if paths is None:
        paths, warnings = checkpoint_candidates(root, cancelled=cancelled)
    paths = tuple(islice(paths, MAX_FILES + 1))
    if not 1 <= len(paths) <= MAX_FILES:
        raise ValueError("请选择 1–2000 个文件。")
    _validate_paths(paths)
    if any(present and path not in paths for path, present in markers.items()):
        raise ValueError("选择必须包含现有 Block 元数据；不能把未知 Block 项目当作普通源码复制。")
    files, observations, total = {}, [], 0
    for path in sorted(paths):
        payload, observed = _read_file(root, path, cancelled)
        total += len(payload)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("所选原件超过 256 MiB。")
        files[path] = payload
        observations.append((path, observed))
    kind, candidate, unmapped = _candidate(root, files)
    _validate_paths(candidate)
    if len(candidate) > MAX_FILES:
        raise ValueError("转换后的文件超过 2000 项。")
    output_size = sum(len(b) for b in candidate.values())
    if output_size + (total if kind == "legacy-conversion" else 0) > MAX_TOTAL_BYTES:
        raise ValueError("新副本与独立原件超过 256 MiB。")
    warnings += ("仅复制已勾选且实际读到的本地文件；不证明依赖完整或云端文件均已下载。",)
    if kind == "legacy-conversion":
        warnings += ("旧 LaTeX 片段原文保留于 Block，但 trusted=false；不会自动进入编译输出。",
                     "副本中被重新生成的路径与全部选定原件分开保留；请先比较，再决定是否切换。")
    for path, observed in observations:
        payload, again = _read_file(root, path, cancelled)
        if payload != files[path] or again != observed:
            raise OSError("迁移输入在读取时变化；请重新审阅，原件保留。")
    for path, observed in observations:
        _cancel(cancelled)
        _check_signature(root, path, observed)
    current = root.lstat()
    if (not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != identity
            or _project_markers(root) != markers):
        raise OSError("项目目录或格式标记在读取时变化。")
    review = MigrationReview(root, kind, tuple(files.items()), tuple(sorted(candidate.items())),
                             tuple(observations), identity, unmapped, warnings)
    if expected is not None and any(getattr(review, key) != getattr(expected, key) for key in
            ("project", "kind", "original", "candidate", "observations", "identity", "unmapped_keys")):
        raise OSError("项目在审阅后变化；没有发布迁移结果。")
    return review


def migrate_project_copy(review, target, *, drafts=(), cancelled=None):
    """Publish exactly the reviewed selection outside the source, never switch."""
    _cancel(cancelled)
    fresh = inspect_project_migration(review.project, paths=[p for p, _ in review.original],
                                      cancelled=cancelled, expected=review)
    destination = Path(target).expanduser().absolute()
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.is_relative_to(fresh.project):
        raise ValueError("请选择原项目之外、尚不存在的新目录。")
    drafts = tuple(islice(drafts, MAX_DRAFTS + 1))
    if len(drafts) > MAX_DRAFTS:
        raise ValueError("独立草稿超过 200 项。")
    original_drafts = [{"id": d.id, "kind": d.kind, "target": d.target} for d in drafts]
    if fresh.kind == "legacy-conversion":
        # An old main.tex draft is not a draft of newly generated main.tex.
        # Keep bytes but require an independent, explicit destination on resume.
        drafts = tuple(replace(d, target=None) if d.target in fresh.replaced else d for d in drafts)
    info = CheckpointInfo(datetime.now(timezone.utc).isoformat(),
        tuple(FileEntry(p, _sha(b), len(b)) for p, b in fresh.candidate), _draft_entries(drafts))
    payloads = [("project/" + p, b) for p, b in fresh.candidate]
    payloads += [("drafts/" + d.id + _DRAFT_SUFFIX[d.kind], d.payload) for d in drafts]
    if fresh.kind == "legacy-conversion":
        payloads += [("recovery-evidence/original/" + p, b) for p, b in fresh.original]
    report = {"format": "icstex-reviewed-project-copy", "version": 1, "kind": fresh.kind,
        "scope": _COPY_SCOPE, "original_project": _ORIGINAL_POLICY,
        "original_drafts": original_drafts,
        "unmapped_legacy_fields": fresh.unmapped_keys,
        "replaced_in_copy": fresh.replaced,
        "originals": [{"path": p, "sha256": _sha(b), "size": len(b)} for p, b in fresh.original],
        "output": [{"path": p, "sha256": _sha(b), "size": len(b)} for p, b in fresh.candidate],
        "warnings": tuple(dict.fromkeys((*review.warnings, *fresh.warnings)))}
    payloads.append(("recovery-evidence/decision.json", _json_bytes(report)))
    if len(info.manifest()) > MAX_MANIFEST_BYTES or sum(len(b) for _, b in payloads) > MAX_TOTAL_BYTES:
        raise ValueError("新副本与独立原件/草稿超过 256 MiB 上限。")
    def recheck():
        inspect_project_migration(fresh.project, paths=[p for p, _ in fresh.original],
                                  cancelled=cancelled, expected=fresh)
    return _publish_restore(info, target, payloads, cancelled=cancelled, check_source=recheck)


@dataclass(frozen=True)
class MigrationCopy:
    copy: RecoveryCopy
    kind: str
    originals: tuple[tuple[str, bytes], ...]
    unmapped_keys: tuple[str, ...]
    replaced: tuple[str, ...]


def read_migration_copy(directory, *, cancelled=None, expected=None):
    """Verify the output AND its retained originals/decision before a UI switch.

    Digests prove content consistency, not authorship or authenticity. Extra build
    output is not covered; listed original evidence is rechecked with the copy.
    """
    copy = read_recovery_copy(directory, cancelled=cancelled,
                              expected=expected.copy if expected else None)
    raw, observation = _read_file(copy.directory, "recovery-evidence/decision.json", cancelled)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError("迁移决定超过 4 MiB。")
    report = _json(raw)
    keys = {"format", "version", "kind", "scope", "original_project", "unmapped_legacy_fields",
            "replaced_in_copy", "originals", "output", "warnings", "original_drafts"}
    if (not isinstance(report, dict) or set(report) != keys
            or report["format"] != "icstex-reviewed-project-copy"
            or type(report["version"]) is not int or report["version"] != 1
            or report["kind"] not in {"source-copy", "block-copy", "legacy-conversion"}
            or report["scope"] != _COPY_SCOPE or report["original_project"] != _ORIGINAL_POLICY
            or not isinstance(report["warnings"], list)
            or any(not isinstance(s, str) for s in report["warnings"])):
        raise ValueError("迁移决定格式未知或不完整；不切换项目。")
    def rows(files):
        return [{"path": p, "sha256": _sha(b), "size": len(b)} for p, b in files]
    if (not isinstance(report["output"], list)
            or any(not isinstance(e, dict) or set(e) != {"path", "sha256", "size"}
                   or type(e["size"]) is not int for e in report["output"])):
        raise ValueError("迁移输出清单字段或长度类型无效。")
    if report["output"] != rows(copy.files):
        raise ValueError("迁移决定与副本清单不一致。")
    original_rows = report["originals"]
    if (not isinstance(original_rows, list) or not 1 <= len(original_rows) <= MAX_FILES
            or any(not isinstance(e, dict) or set(e) != {"path", "sha256", "size"}
                   or type(e["size"]) is not int or not 0 <= e["size"] <= MAX_FILE_BYTES
                   or not isinstance(e["sha256"], str) or not _DIGEST.fullmatch(e["sha256"])
                   for e in original_rows)):
        raise ValueError("迁移原件清单无效。")
    _validate_paths([e["path"] for e in original_rows])
    evidence = [("recovery-evidence/decision.json", raw, observation)]
    originals = []
    total = sum(e.size for e in (*copy.info.files, *copy.info.drafts)) + len(raw)
    for entry in original_rows:
        if report["kind"] == "legacy-conversion":
            path = "recovery-evidence/original/" + entry["path"]
            payload, observed = _read_file(copy.directory, path, cancelled)
            total += len(payload)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("迁移副本和原件证据超过 256 MiB。")
            evidence.append((path, payload, observed))
        else:
            payload = dict(copy.files).get(entry["path"])
        if payload is None or len(payload) != entry["size"] or _sha(payload) != entry["sha256"]:
            raise ValueError("迁移原件摘要或长度不符。")
        originals.append((entry["path"], payload))
    kind, candidate, unmapped = _candidate(copy.project, dict(originals))
    replaced = tuple(p for p, b in sorted(candidate.items())
                     if p in dict(originals) and dict(originals)[p] != b)
    if (kind != report["kind"] or candidate != dict(copy.files)
            or list(unmapped) != report["unmapped_legacy_fields"]
            or list(replaced) != report["replaced_in_copy"]):
        raise ValueError("保留原件不能生成所声明的副本或迁移决定；不切换项目。")
    draft_targets = report["original_drafts"]
    if not isinstance(draft_targets, list) or len(draft_targets) != len(copy.info.drafts):
        raise ValueError("独立草稿的迁移目标记录不完整。")
    for original, entry in zip(draft_targets, copy.info.drafts):
        if (not isinstance(original, dict) or set(original) != {"id", "kind", "target"}
                or original["id"] != entry.id or original["kind"] != entry.kind):
            raise ValueError("独立草稿身份不一致。")
        target = original["target"]
        if target is not None:
            _relative(target)
        mapped = None if kind == "legacy-conversion" and target in replaced else target
        if entry.target != mapped:
            raise ValueError("旧草稿不能自动覆盖副本中重新生成的文件。")
    for path, payload, observed in evidence:
        again, current = _read_file(copy.directory, path, cancelled)
        if again != payload or current != observed:
            raise OSError("迁移证据在读取时变化；请重新审阅。")
    copy = replace(copy, observations=copy.observations + tuple((p, o) for p, _, o in evidence))
    check_recovery_identity(copy, cancelled=cancelled)
    result = MigrationCopy(copy, kind, tuple(originals), unmapped, replaced)
    if expected is not None and result != expected:
        raise OSError("迁移副本或证据在确认后变化；不切换项目。")
    return result
