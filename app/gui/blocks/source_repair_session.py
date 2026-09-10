"""One source, all linked tables, one explicit in-memory Undo transaction."""
from copy import deepcopy
from dataclasses import dataclass, replace

from PySide6.QtGui import QUndoCommand

from app.core.blocks.property_draft import apply_table_projection, table_projection
from app.core.blocks.schema import validate_block
from app.core.blocks.source_repair import capture_path_unchanged
from app.core.blocks.table_model import TableData


@dataclass(frozen=True)
class SourceRepairSnapshot:
    project: object
    sources: tuple
    record: object
    blocks: dict
    drafts: dict
    draft_revision: int
    local_tables: dict

    @classmethod
    def capture(cls, session, source_id):
        session.finish_editor_inputs.emit()
        if session._closed or session.project_dir is None:
            raise ValueError("项目已关闭或尚未保存到目录。")
        if session.save_error:
            raise ValueError("请先处理当前保存冲突或恢复提示，再合并来源；所有内容保留。")
        matches = [record for record in session.sources if record.sourceId == source_id]
        if len(matches) != 1:
            raise ValueError("来源记录缺失或 ID 重复，未创建修复。")
        blocks = {b.id: deepcopy(b.to_dict()) for b in session.registry.blocks()
                  if b.provenance.sourceId == source_id}
        if not blocks or len(blocks) > 20:
            raise ValueError("本次修复须包含 1–20 个关联表格，不能遗漏同来源对象。")
        local, drafts, cells = {}, {}, 0
        for block_id, block in blocks.items():
            if block["type"] != "table" or validate_block(block):
                raise ValueError("来源含非表格或未知格式对象，不能推进整个来源的基线。")
            initial = table_projection(block["content"])
            for key, draft in session.editor_drafts.items():
                if draft.target_id == block_id:
                    if key != ("table", block_id) or draft.base != block:
                        raise ValueError("关联对象还有未完成的属性/单元格编辑或冲突，请先处理；草稿保留。")
                    drafts[key] = deepcopy(draft)
            draft = drafts.get(("table", block_id))
            data = TableData.from_content_dict(table_projection(draft.values) if draft else initial)
            local[block_id] = data
            cells += len(data.rows) * len(data.columns)
        if cells > 100000:
            raise ValueError("关联表格合计超过本次 100000 个单元格的修复上限。")
        return cls(session.project_dir, tuple(session.sources), matches[0], blocks, drafts,
                   session.editor_draft_revision, local)

    def validate(self, session):
        if (session._closed or session.project_dir != self.project or tuple(session.sources) != self.sources
                or session.editor_draft_revision != self.draft_revision):
            raise ValueError("项目、来源或编辑草稿已变化，请重新比较；尚未应用。")
        current = {b.id: b.to_dict() for b in session.registry.blocks()
                   if b.provenance.sourceId == self.record.sourceId}
        drafts = {key: draft for key, draft in session.editor_drafts.items() if draft.target_id in self.blocks}
        if repr(current) != repr(self.blocks) or repr(drafts) != repr(self.drafts):
            raise ValueError("关联对象已变化、增加或删除，请重新比较；尚未应用。")

    def patches(self, candidates):
        if set(candidates) != set(self.blocks):
            raise ValueError("必须先确认此来源的每个关联表格，不能部分推进来源基线。")
        patches = {}
        cells = 0
        for block_id, data in candidates.items():
            after = table_projection(data.to_content_dict())
            cells += len(data.rows) * len(data.columns)
            original = self.blocks[block_id]["content"]
            content = apply_table_projection(original, table_projection(original), after)
            block = {**self.blocks[block_id], "content": content}
            if validate_block(block):
                raise ValueError("合并结果不能保存为当前 Block 格式；原内容保留。")
            patches[block_id] = content
        if cells > 100000:
            raise ValueError("候选合计超过本次 100000 个单元格的修复上限。")
        return patches

    def apply_verified(self, session, candidates, baseline, remote):
        """Called immediately after the worker rehashes BOTH immutable captures.

        Cheap path tokens close the queued-callback gap. This is not an OS lock
        on arbitrary external writers; later edits remain a new source version.
        Disk persistence still uses the existing guarded Block writer.
        """
        session.finish_editor_inputs.emit()
        self.validate(session)
        if (baseline.project != self.project or remote.project != self.project
                or baseline.sha256 != self.record.baseSha256.lower()
                or remote.relative_path != self.record.relativePath
                or not capture_path_unchanged(baseline) or not capture_path_unchanged(remote)):
            raise ValueError("来源或基线在确认期间变化，请重新比较；尚未应用。")
        patches = self.patches(candidates)
        if (not self.drafts and remote.sha256 == self.record.baseSha256
                and all(repr(value) == repr(self.blocks[key]["content"]) for key, value in patches.items())):
            return False
        session.undo_stack.push(_ApplySourceRepairCommand(session, self, patches, remote.sha256))
        return True


class _ApplySourceRepairCommand(QUndoCommand):
    def __init__(self, session, snapshot, patches, remote_sha):
        super().__init__("合并来源到全部关联表格")
        self.session = session
        self.snapshot = snapshot
        self.before = {key: deepcopy(block["content"]) for key, block in snapshot.blocks.items()}
        self.after = deepcopy(patches)
        self.new_record = replace(snapshot.record, baseSha256=remote_sha)
        self.consumable = deepcopy(snapshot.drafts)

    def _model(self, contents, record):
        for block_id, content in contents.items():
            self.session.registry.update(block_id, {"content": deepcopy(content)})
        self.session.sources[:] = [record if item.sourceId == record.sourceId else item
                                   for item in self.session.sources]

    def redo(self):
        for key, draft in self.consumable.items():
            if self.session.editor_drafts.get(key) == draft:
                del self.session.editor_drafts[key]
        self._model(self.after, self.new_record)
        self.session.notify_model_changed("source_repair_applied")
        self.session._editor_drafts_updated()

    def undo(self):
        self._model(self.before, self.snapshot.record)
        self.consumable = {}
        for key, draft in self.snapshot.drafts.items():
            if key not in self.session.editor_drafts:
                block = self.session.registry.get(draft.target_id)
                restored = replace(deepcopy(draft), base=deepcopy(block.to_dict()))
                self.session.editor_drafts[key] = restored
                self.consumable[key] = restored
        # Newer drafts, including reentrant input, are never erased by undo/redo.
        self.session.notify_model_changed("source_repair_undone")
        self.session._editor_drafts_updated()
