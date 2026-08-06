"""Block data model (Modular Layout MVP Sprint 1).

Blocks carry content and paper semantics only; layout and theme information
must never be stored on a Block. IDs are immutable; alias and label are
mutable and never referenced internally (references always point at IDs).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


SCHEMA_VERSION = "1.0.0"

BLOCK_TYPES: tuple[str, ...] = (
    "text",
    "formula",
    "image",
    "table",
    "list",
    "heading",
    "quote",
    "rawLatex",
)

BlockType = Literal[
    "text",
    "formula",
    "image",
    "table",
    "list",
    "heading",
    "quote",
    "rawLatex",
]

REFERENCE_KINDS: tuple[str, ...] = (
    "citation",
    "cross-reference",
    "dependency",
    "source",
)


@dataclass(frozen=True)
class Caption:
    text: str
    shortText: str | None = None


@dataclass(frozen=True)
class Semantic:
    role: str
    label: str | None = None
    caption: Caption | None = None
    numbering: str = "auto"


@dataclass(frozen=True)
class Provenance:
    kind: str = "created"
    sourceId: str | None = None
    importedAt: str | None = None


@dataclass(frozen=True)
class BlockReference:
    targetBlockId: str
    kind: str = "cross-reference"
    display: str | None = None
    customText: str | None = None


@dataclass
class Block:
    schemaVersion: str = SCHEMA_VERSION
    id: str = ""
    type: str = "text"
    alias: str = ""
    semantic: Semantic = field(default_factory=Semantic)
    content: dict = field(default_factory=dict)
    references: list[BlockReference] = field(default_factory=list)
    provenance: Provenance = field(default_factory=Provenance)
    revision: int = 1
    metadata: dict = field(default_factory=dict)
    extensions: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schemaVersion": self.schemaVersion,
            "id": self.id,
            "type": self.type,
            "alias": self.alias,
            "semantic": {
                "role": self.semantic.role,
                "label": self.semantic.label,
                "caption": (
                    {
                        "text": self.semantic.caption.text,
                        "shortText": self.semantic.caption.shortText,
                    }
                    if self.semantic.caption is not None
                    else None
                ),
                "numbering": self.semantic.numbering,
            },
            "content": self.content,
            "references": [
                {
                    "targetBlockId": reference.targetBlockId,
                    "kind": reference.kind,
                    "display": reference.display,
                    "customText": reference.customText,
                }
                for reference in self.references
            ],
            "provenance": {
                "kind": self.provenance.kind,
                "sourceId": self.provenance.sourceId,
                "importedAt": self.provenance.importedAt,
            },
            "revision": self.revision,
            "metadata": self.metadata,
            "extensions": self.extensions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        semantic_data = data.get("semantic", {}) or {}
        caption_data = semantic_data.get("caption")
        references = [
            BlockReference(
                targetBlockId=item["targetBlockId"],
                kind=item.get("kind", "cross-reference"),
                display=item.get("display"),
                customText=item.get("customText"),
            )
            for item in data.get("references", [])
        ]
        provenance_data = data.get("provenance", {}) or {}
        return cls(
            schemaVersion=data.get("schemaVersion", SCHEMA_VERSION),
            id=data.get("id", ""),
            type=data.get("type", "text"),
            alias=data.get("alias", ""),
            semantic=Semantic(
                role=semantic_data.get("role", ""),
                label=semantic_data.get("label"),
                caption=(
                    Caption(
                        text=caption_data.get("text", ""),
                        shortText=caption_data.get("shortText"),
                    )
                    if caption_data is not None
                    else None
                ),
                numbering=semantic_data.get("numbering", "auto"),
            ),
            content=data.get("content", {}),
            references=references,
            provenance=Provenance(
                kind=provenance_data.get("kind", "created"),
                sourceId=provenance_data.get("sourceId"),
                importedAt=provenance_data.get("importedAt"),
            ),
            revision=int(data.get("revision", 1)),
            metadata=data.get("metadata", {}) or {},
            extensions=data.get("extensions", {}) or {},
        )


def content_for_text(text: str) -> dict:
    return {"format": "plain", "text": text}


def content_for_heading(text: str, level: int = 1) -> dict:
    return {"text": text, "level": max(1, min(6, int(level)))}


def content_for_quote(text: str) -> dict:
    return {"text": text}


def content_for_list(items: list[str], ordered: bool = False) -> dict:
    return {"ordered": bool(ordered), "items": [str(item) for item in items]}


def content_for_raw_latex(latex: str) -> dict:
    return {"latex": latex, "trusted": False}
