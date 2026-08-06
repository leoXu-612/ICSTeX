"""Compile-error source mapping (Sprint 5).

The renderer emits machine comments around every Block; this module builds a
line -> Block map from the generated LaTeX so a LaTeX error line can be
attributed to the Block and layout slot that produced it.
"""
from __future__ import annotations

import re


_BEGIN_RE = re.compile(r"% ICSTEX:BEGIN block=(\S+)")
_END_RE = re.compile(r"% ICSTEX:END block=(\S+)")
_SLOT_RE = re.compile(r"% ICSTEX:slot=(\S+) block=(\S+)")
_LAYOUT_RE = re.compile(r"% ICSTEX:layout=(\S+)")


def build_source_map(tex_text: str) -> dict:
    """Return {blockId: {"start_line", "end_line", "layout_id", "slot_instance_id"}}."""

    lines = tex_text.splitlines()
    current_layout: str | None = None
    current_slot: str | None = None
    stack: list[str] = []
    ranges: dict[str, dict] = {}
    for index, line in enumerate(lines, start=1):
        layout_match = _LAYOUT_RE.search(line)
        if layout_match:
            current_layout = layout_match.group(1)
        slot_match = _SLOT_RE.search(line)
        if slot_match:
            current_slot = slot_match.group(1)
        begin_match = _BEGIN_RE.search(line)
        end_match = _END_RE.search(line)
        if begin_match:
            block_id = begin_match.group(1)
            stack.append(block_id)
            ranges[block_id] = {
                "start_line": index,
                "end_line": index,
                "layout_id": current_layout,
                "slot_instance_id": current_slot,
            }
        if end_match and stack:
            block_id = end_match.group(1)
            if block_id in ranges:
                ranges[block_id]["end_line"] = index
            if stack and stack[-1] == block_id:
                stack.pop()
    return ranges


def block_at_line(tex_text: str, line: int) -> dict | None:
    for block_id, span in build_source_map(tex_text).items():
        if span["start_line"] <= line <= span["end_line"]:
            return {"blockId": block_id, **span}
    return None
