"""Block-based modular document model (Modular Layout MVP Sprint 1).

Pure core rules with no Qt/filesystem dependency in the model layer: stable
IDs, Block model, JSON Schema (Draft 2020-12) validation, registry, atomic
store, migration framework, and the formula adapter over the existing
``app.core.formula_tree`` engine.
"""
from __future__ import annotations

from app.core.blocks.model import (
    BLOCK_TYPES,
    Block,
    BlockReference,
    BlockType,
    Caption,
    Provenance,
    Semantic,
    content_for_heading,
    content_for_list,
    content_for_quote,
    content_for_raw_latex,
    content_for_text,
)
from app.core.blocks.registry import BlockRegistry, ValidationIssue
from app.core.blocks.store import BlockStore

__all__ = [
    "BLOCK_TYPES",
    "Block",
    "BlockReference",
    "BlockRegistry",
    "BlockStore",
    "BlockType",
    "Caption",
    "Provenance",
    "Semantic",
    "ValidationIssue",
    "content_for_heading",
    "content_for_list",
    "content_for_quote",
    "content_for_raw_latex",
    "content_for_text",
]
