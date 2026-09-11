"""Read a recovery copy and prepare independent drafts; never write or compile."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import stat

from app.core.project_checkpoint import (
    CheckpointInfo, _DRAFT_SUFFIX, _cancel, _check_signature, _parse_manifest,
    _read_file, _unique_object, MAX_DRAFT_BYTES,
)
from app.core.blocks.layout import LayoutNode
from app.core.blocks.model import SCHEMA_VERSION
from app.core.blocks.property_draft import PropertyDraft, table_projection
from app.core.blocks.schema import validate_block, validate_layout, validate_source
from app.core.blocks.source_registry import SourceRecord
from app.core.blocks.store import BlockStore
from app.core.blocks.theme import theme_from_dict


@dataclass(frozen=True)
class RecoveryCopy:
    directory: Path
    info: CheckpointInfo
    files: tuple[tuple[str, bytes], ...]
    drafts: tuple[tuple[str, bytes], ...]
    observations: tuple[tuple[str, tuple], ...]
    identity: tuple[int, int]

    @property
    def project(self):
        return self.directory / "project"


def check_recovery_identity(copy: RecoveryCopy, *, cancelled=None):
    current = copy.directory.lstat()
    if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != copy.identity:
        raise OSError("恢复副本目录已变化；没有载入或保存草稿。")
    for relative, observation in copy.observations:
        _cancel(cancelled)
        _check_signature(copy.directory, relative, observation)


def read_recovery_copy(directory, *, cancelled=None, expected=None) -> RecoveryCopy:
    """Verify all manifest-listed bytes twice, retaining immutable input bytes.

    Unlisted files are not covered. This is content verification, not proof of
    archive authenticity or a reservation against uncooperating external writers.
    """
    raw = Path(directory).expanduser().absolute()
    if raw.is_symlink() or raw.name.startswith(".icstex-restore.incomplete-"):
        raise ValueError("不能把链接或未完成的恢复目录作为已核验副本。")
    root = raw.resolve(strict=True)
    initial = root.lstat()
    manifest, observation = _read_file(root, "manifest.json", cancelled)
    info = _parse_manifest(manifest)
    if expected is not None and (root != expected.directory or info != expected.info):
        raise ValueError("恢复清单在审阅后变化；请重新审阅。")
    values = [("manifest.json", manifest, observation)]
    files, drafts = [], []
    for entry in (*info.files, *info.drafts):
        is_draft = hasattr(entry, "id")
        relative = ("drafts/" + entry.id + _DRAFT_SUFFIX[entry.kind] if is_draft else "project/" + entry.path)
        payload, observation = _read_file(root, relative, cancelled)
        if len(payload) != entry.size or hashlib.sha256(payload).hexdigest() != entry.sha256:
            raise ValueError(f"恢复副本摘要或长度不符：{relative}；原件保留。")
        if is_draft:
            payload.decode("utf-8")
        (drafts if is_draft else files).append((entry.id if is_draft else entry.path, payload))
        values.append((relative, payload, observation))
    for relative, payload, observation in values:
        again, identity = _read_file(root, relative, cancelled)
        if again != payload or identity != observation:
            raise OSError(f"恢复副本在读取时变化：{relative}")
    result = RecoveryCopy(root, info, tuple(files), tuple(drafts),
                          tuple((path, observation) for path, _, observation in values),
                          (initial.st_dev, initial.st_ino))
    check_recovery_identity(result, cancelled=cancelled)
    return result


def _json(payload):
    if len(payload) > MAX_DRAFT_BYTES:
        raise ValueError("恢复草稿超过 16 MiB 上限。")
    return json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite draft JSON")))


def parse_block_model(model):
    """Use existing schemas; refuse lossy/unknown envelopes before GUI creation."""
    if not isinstance(model, dict) or set(model) != {"blocks", "layout", "sources", "document_theme"}:
        raise ValueError("未知 Block 恢复模型；保留原始 JSON，不自动迁移。")
    registry = BlockStore.from_bytes(json.dumps({"format": "icstex-blocks",
        "schemaVersion": SCHEMA_VERSION, "blocks": model["blocks"]}).encode("utf-8"))
    raw_layout = model["layout"]
    if raw_layout is not None and validate_layout(raw_layout):
        raise ValueError("恢复布局格式无效。")
    layout = LayoutNode.from_dict(raw_layout) if raw_layout is not None else None
    if not isinstance(model["sources"], list) or any(validate_source(item) for item in model["sources"]):
        raise ValueError("恢复来源格式无效。")
    sources = [SourceRecord.from_dict(item) for item in model["sources"]]
    raw_theme = model["document_theme"]
    # Persisted DocumentTheme supports empty/partial override dictionaries; the
    # full-theme schema requires defaults which these real sessions do not store.
    if (not isinstance(raw_theme, dict) or raw_theme.get("kind") != "document-theme"
            or raw_theme.get("schemaVersion") != SCHEMA_VERSION
            or not all(isinstance(raw_theme.get(key), dict) for key in
                       ("page", "typography", "headings", "figures", "tables", "layout"))
            or not all(isinstance(raw_theme.get(key), str) for key in ("id", "name"))):
        raise ValueError("恢复文档主题格式无效。")
    theme = theme_from_dict(raw_theme)
    projected = {"blocks": [b.to_dict() for b in registry.blocks()],
                 "layout": layout.to_dict() if layout else None,
                 "sources": [s.to_dict() for s in sources], "document_theme": theme.to_dict()}
    if projected != model:
        raise ValueError("恢复模型不能无损载入；原 JSON 保留，不进行隐式迁移。")
    return {"registry": registry, "layout": layout, "sources": sources, "document_theme": theme}


def parse_block_draft(payload):
    try:
        value = _json(payload)
        if (not isinstance(value, dict) or set(value) != {"format", "version", "model", "unapplied"}
                or value["format"] != "icstex-block-draft" or type(value["version"]) is not int
                or value["version"] != 1 or not isinstance(value["unapplied"], list)):
            raise ValueError("未知 Block 草稿版本；原件保留。")
        model = parse_block_model(value["model"])
        drafts = {}
        for item in value["unapplied"]:
            draft = PropertyDraft(**item)
            if (draft.kind not in {"block", "layout", "table", "table_cell", "formula"}
                    or not all(isinstance(v, str) and v for v in (draft.target_id, draft.label))
                    or not all(isinstance(v, dict) for v in (draft.base, draft.initial, draft.values))
                    or draft.key in drafts):
                raise ValueError("恢复属性草稿格式或目标重复。")
            validate = validate_layout if draft.kind == "layout" else validate_block
            if validate(draft.base) or draft.base.get("id") != draft.target_id:
                raise ValueError("恢复属性草稿缺少合法的原对象。")
            if draft.kind == "table":
                if any(table_projection(data) != data for data in (draft.initial, draft.values)):
                    raise ValueError("表格草稿含编辑器无法无损载入的字段。")
            if draft.kind == "table_cell":
                for data in (draft.initial, draft.values):
                    if set(data) != {"row", "column", "text"} or not all(isinstance(v, str) for v in data.values()):
                        raise ValueError("单元格恢复草稿字段无效。")
                if any(draft.initial[key] != draft.values[key] for key in ("row", "column")):
                    raise ValueError("单元格恢复目标变化。")
            if draft.kind == "layout":
                for data in (draft.initial, draft.values):
                    if (set(data) != {"gap", "alignment", "strategy"}
                            or type(data["gap"]) not in (int, float)
                            or not all(isinstance(data[key], str) for key in ("alignment", "strategy"))):
                        raise ValueError("布局属性恢复草稿字段无效。")
            if draft.kind == "block":
                for data in (draft.initial, draft.values):
                    if (set(data) - {"alias", "text", "latex", "caption", "widthMm", "heightMm", "level"}
                            or any((key in {"alias", "text", "latex", "caption"} and not isinstance(value, str))
                           or (key in {"widthMm", "heightMm", "level"} and value is not None
                               and type(value) not in (int, float)) for key, value in data.items())):
                        raise ValueError("Block 属性恢复草稿字段无效。")
            drafts[draft.key] = draft
        return model, drafts
    except (KeyError, TypeError, AttributeError, RecursionError, OverflowError) as exc:
        raise ValueError("恢复草稿无法安全载入；原始字节保留。") from exc


def saved_block_model(copy):
    files = dict(copy.files)
    try:
        blocks = _json(files[".icstex/blocks.json"])
        layouts = _json(files[".icstex/layouts.json"])
        sources = _json(files[".icstex/sources.json"])
        if (set(blocks) != {"format", "schemaVersion", "blocks"} or blocks["format"] != "icstex-blocks"
                or blocks["schemaVersion"] != SCHEMA_VERSION
                or set(layouts) != {"schemaVersion", "layouts"} or layouts["schemaVersion"] != SCHEMA_VERSION
                or not isinstance(layouts["layouts"], list) or len(layouts["layouts"]) > 1
                or set(sources) != {"sources"}):
            raise ValueError("磁盘 Block 元数据版本或字段未知，不能建立恢复保存基线。")
        return parse_block_model({"blocks": blocks["blocks"],
            "layout": layouts["layouts"][0] if layouts["layouts"] else None,
            "sources": sources["sources"], "document_theme": _json(files["styles/document-theme.json"])})
    except (KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise ValueError("检查点未包含完整的可编辑 Block 元数据；原件与草稿仍保留。") from exc


def selected_drafts(copy, ids):
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("请明确勾选要继续编辑的草稿。")
    entries = {entry.id: entry for entry in copy.info.drafts}
    if any(key not in entries for key in ids):
        raise ValueError("草稿不在已核验清单中。")
    chosen = tuple(entries[key] for key in ids)
    targets = [entry.target for entry in chosen if entry.target is not None]
    if len(targets) != len(set(targets)):
        raise ValueError("同一文件有多份草稿；请审阅后只选择其中一份。其余草稿仍保留。")
    if any(entry.kind == "block-state" for entry in chosen) and len(chosen) != 1:
        raise ValueError("请单独选择一个 Block 状态，避免与源码草稿互相覆盖；其余草稿仍独立保留。")
    return chosen
