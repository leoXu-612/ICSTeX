"""Block registry: CRUD, stable IDs, reference reverse lookup, validation."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.blocks.ids import new_block_id
from app.core.blocks.model import Block, BlockReference, Provenance, Semantic
from app.core.blocks.schema import validate_block


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str
    message: str
    block_id: str | None = None


@dataclass(frozen=True)
class ReferenceLocation:
    referrer_id: str
    referrer_alias: str
    reference: BlockReference


@dataclass
class CreateBlockInput:
    type: str = "text"
    alias: str = ""
    semantic: object | None = None
    content: dict = field(default_factory=dict)
    references: list[BlockReference] = field(default_factory=list)
    provenance: object | None = None
    metadata: dict = field(default_factory=dict)
    extensions: dict = field(default_factory=dict)


class BlockError(ValueError):
    """Raised when a registry operation violates an invariant."""


class BlockRegistry:
    """Owns Block identity and reference integrity.

    IDs are immutable and generated once at creation; alias renames never
    change references because references always point at IDs.
    """

    def __init__(self, blocks: list[Block] | None = None) -> None:
        self._blocks: dict[str, Block] = {}
        if blocks:
            for block in blocks:
                self._insert(block)

    # --- queries ----------------------------------------------------------

    def get(self, block_id: str) -> Block | None:
        return self._blocks.get(block_id)

    def blocks(self) -> list[Block]:
        return sorted(self._blocks.values(), key=lambda block: block.id)

    def labels(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for block in self._blocks.values():
            label = block.semantic.label
            if label:
                result[label] = block.id
        return result

    def find_references_to(self, block_id: str) -> list[ReferenceLocation]:
        locations: list[ReferenceLocation] = []
        for block in self._blocks.values():
            for reference in block.references:
                if reference.targetBlockId == block_id:
                    locations.append(
                        ReferenceLocation(
                            referrer_id=block.id,
                            referrer_alias=block.alias,
                            reference=reference,
                        )
                    )
        return sorted(locations, key=lambda item: (item.referrer_id, item.reference.kind))

    # --- mutations --------------------------------------------------------

    def create(self, input_: CreateBlockInput) -> Block:
        if not input_.alias.strip():
            raise BlockError("alias 不能为空")
        block = Block(
            id=new_block_id(),
            type=input_.type,
            alias=input_.alias.strip(),
            semantic=input_.semantic if input_.semantic is not None else Semantic(role=input_.type),
            content=input_.content,
            references=list(input_.references),
            provenance=input_.provenance if input_.provenance is not None else Provenance(),
            revision=1,
            metadata=dict(input_.metadata),
            extensions=dict(input_.extensions),
        )
        self._insert(block)
        return block

    def update(self, block_id: str, patch: dict) -> Block:
        block = self._require(block_id)
        alias = patch.get("alias", block.alias)
        semantic = patch.get("semantic", block.semantic)
        if not str(alias).strip():
            raise BlockError("alias 不能为空")
        label = semantic.label if semantic is not None else block.semantic.label
        self._ensure_label_unique(label, exclude_id=block_id)
        block.alias = str(alias).strip()
        if semantic is not None:
            block.semantic = semantic
        if "content" in patch:
            block.content = patch["content"]
        if "references" in patch:
            block.references = list(patch["references"])
        if "metadata" in patch:
            block.metadata = dict(patch["metadata"])
        if "extensions" in patch:
            block.extensions = dict(patch["extensions"])
        block.revision += 1
        return block

    def rename_alias(self, block_id: str, alias: str) -> Block:
        return self.update(block_id, {"alias": alias})

    def remove(self, block_id: str, strategy: str = "reject-if-referenced") -> None:
        self._require(block_id)
        references = self.find_references_to(block_id)
        if references:
            if strategy == "reject-if-referenced":
                names = ", ".join(f"{item.referrer_alias} ({item.referrer_id})" for item in references)
                raise BlockError(f"Block 仍被引用，无法删除：{names}")
            if strategy == "replace-with-placeholder":
                placeholder = self.create(
                    CreateBlockInput(
                        type="rawLatex",
                        alias="已删除内容",
                        content={"latex": "\\text{[已删除内容]}", "trusted": False},
                    )
                )
                for item in references:
                    referrer = self._blocks[item.referrer_id]
                    referrer.references = [
                        (
                            BlockReference(
                                targetBlockId=placeholder.id,
                                kind=reference.kind,
                                display=reference.display,
                                customText=reference.customText,
                            )
                            if reference.targetBlockId == block_id
                            else reference
                        )
                        for reference in referrer.references
                    ]
                    referrer.revision += 1
        del self._blocks[block_id]

    # --- validation -------------------------------------------------------

    def validate_all(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        seen_ids: set[str] = set()
        seen_labels: dict[str, str] = {}
        for block in self.blocks():
            schema_issues = validate_block(block.to_dict())
            issues.extend(
                ValidationIssue(
                    code="BLOCK_SCHEMA",
                    severity="error",
                    message=message,
                    block_id=block.id,
                )
                for message in schema_issues
            )
            if block.id in seen_ids:
                issues.append(
                    ValidationIssue(
                        code="BLOCK_ID_DUPLICATE",
                        severity="error",
                        message=f"重复的 Block id：{block.id}",
                        block_id=block.id,
                    )
                )
            seen_ids.add(block.id)
            if not block.alias.strip():
                issues.append(
                    ValidationIssue(
                        code="BLOCK_ALIAS_EMPTY",
                        severity="error",
                        message="alias 不能为空",
                        block_id=block.id,
                    )
                )
            label = block.semantic.label
            if label:
                if label in seen_labels:
                    issues.append(
                        ValidationIssue(
                            code="BLOCK_LABEL_DUPLICATE",
                            severity="error",
                            message=f"LaTeX label 重复：{label}",
                            block_id=block.id,
                        )
                    )
                seen_labels[label] = block.id
            for reference in block.references:
                if reference.targetBlockId not in self._blocks:
                    issues.append(
                        ValidationIssue(
                            code="REF_TARGET_MISSING",
                            severity="error",
                            message=f"引用目标不存在：{reference.targetBlockId}",
                            block_id=block.id,
                        )
                    )
        return issues

    # --- internal ---------------------------------------------------------

    def _insert(self, block: Block) -> None:
        if block.id in self._blocks:
            raise BlockError(f"重复的 Block id：{block.id}")
        if not block.alias.strip():
            raise BlockError(f"Block {block.id} 的 alias 不能为空")
        self._ensure_label_unique(block.semantic.label, exclude_id=block.id)
        self._blocks[block.id] = block

    def _ensure_label_unique(self, label: str | None, *, exclude_id: str) -> None:
        if not label:
            return
        for block_id, other in self._blocks.items():
            if block_id != exclude_id and other.semantic.label == label:
                raise BlockError(f"LaTeX label 重复：{label}")

    def _require(self, block_id: str) -> Block:
        block = self._blocks.get(block_id)
        if block is None:
            raise BlockError(f"Block 不存在：{block_id}")
        return block
