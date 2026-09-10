"""Atomic persistence for a Block registry (`.icstex/blocks.json`)."""
from __future__ import annotations

import json
import os
from pathlib import Path

from app.core.blocks.model import SCHEMA_VERSION, Block
from app.core.blocks.registry import BlockError, BlockRegistry
from app.core.blocks.schema import validate_block


class BlockStoreError(ValueError):
    pass


class BlockStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.is_file()

    def save(self, registry: BlockRegistry) -> None:
        issues = registry.validate_all()
        if issues:
            raise BlockStoreError("拒绝保存无效 Block 数据：" + "; ".join(issue.message for issue in issues[:5]))
        payload = {
            "format": "icstex-blocks",
            "schemaVersion": SCHEMA_VERSION,
            "blocks": [block.to_dict() for block in registry.blocks()],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    def load(self) -> BlockRegistry:
        if not self.exists():
            return BlockRegistry()
        try:
            return self.from_bytes(self.path.read_bytes())
        except OSError as exc:
            raise BlockStoreError(f"Block 数据无法读取：{exc}") from exc

    @staticmethod
    def from_bytes(data: bytes) -> BlockRegistry:
        try:
            payload = json.loads(data.decode("utf-8"))
        except (OSError, ValueError) as exc:
            raise BlockStoreError(f"Block 数据无法解析：{exc}") from exc
        if not isinstance(payload, dict) or payload.get("schemaVersion", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise BlockStoreError("不支持的 Block 元数据格式或版本。")
        if payload.get("format") != "icstex-blocks":
            raise BlockStoreError("不是有效的 icstex-blocks 文件。")
        if not isinstance(payload.get("blocks", []), list):
            raise BlockStoreError("blocks 必须是列表。")
        blocks: list[Block] = []
        for raw in payload.get("blocks", []):
            if not isinstance(raw, dict):
                raise BlockStoreError("每个 Block 必须是对象。")
            schema_issues = validate_block(raw)
            if schema_issues:
                raise BlockStoreError(
                    f"Block Schema 校验失败（{raw.get('id', '?')}）：" + "; ".join(schema_issues[:3])
                )
            blocks.append(Block.from_dict(raw))
        try:
            return BlockRegistry(blocks)
        except BlockError as exc:
            raise BlockStoreError(str(exc)) from exc
