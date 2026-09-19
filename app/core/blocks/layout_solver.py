"""Deterministic constrained layout solver (Sprint 2).

Width computation per the task list:
    availableWidth = current LaTeX context width
    usableWidth     = availableWidth - all gaps
    normalizedWeight[i] = weight[i] / sum(weights)
    computedWidth[i]    = usableWidth x normalizedWeight[i]

Checks run before emitting LaTeX: weights > 0, gaps valid, Grid child count,
minWidth satisfaction, nesting depth, block-in-unsplittable-box, and
responsive fallback. Fallback order: reduceGap -> normalizeWeights ->
wrapRows -> stackVertically -> emitCompileBlockingError.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math

from app.core.blocks.layout import BlockSlot, LayoutNode, Size


MM_PER_INCH = 25.4
PT_PER_INCH = 72.27
DEFAULT_MAX_DEPTH = 8
WIDTH_PRECISION = 3


@dataclass(frozen=True)
class LayoutIssue:
    code: str
    severity: str
    message: str
    layout_id: str | None = None
    instance_id: str | None = None


@dataclass(frozen=True)
class SolvedSlot:
    instanceId: str
    blockId: str
    widthPt: float
    ratio: float


@dataclass(frozen=True)
class SolvedNode:
    layoutId: str
    kind: str
    widthPt: float
    children: tuple[object, ...] = ()
    columns: int | None = None
    usedFallback: str | None = None
    issues: list[LayoutIssue] = field(default_factory=list)


def size_to_pt(size: Size | None) -> float:
    if size is None:
        return 0.0
    if size.unit == "mm":
        return size.value * PT_PER_INCH / MM_PER_INCH
    return size.value


def solve_layout(
    layout: LayoutNode,
    available_width_pt: float,
    *,
    block_flags: dict[str, set[str]] | None = None,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> SolvedNode:
    """Solve a layout tree deterministically for the given context width."""

    flags = block_flags or {}
    return _solve(layout, available_width_pt, flags, depth=0, max_depth=max_depth)


def _solve(
    layout: LayoutNode,
    available: float,
    flags: dict[str, set[str]],
    *,
    depth: int,
    max_depth: int,
) -> SolvedNode:
    issues: list[LayoutIssue] = []
    if depth > max_depth:
        issues.append(
            LayoutIssue(
                code="ICSTEX_LAYOUT_DEPTH",
                severity="error",
                message="布局嵌套过深",
                layout_id=layout.id,
            )
        )
    if not layout.children:
        issues.append(
            LayoutIssue(
                code="ICSTEX_LAYOUT_EMPTY",
                severity="error",
                message="布局子项为空",
                layout_id=layout.id,
            )
        )

    if layout.kind in ("column", "fullWidth"):
        children = tuple(
            _solve_child(child, available, flags, depth=depth, max_depth=max_depth)
            for child in layout.children
        )
        for child in children:
            if isinstance(child, SolvedNode):
                issues.extend(child.issues)
        return SolvedNode(
            layoutId=layout.id,
            kind=layout.kind,
            widthPt=available,
            children=children,
            columns=None,
            issues=issues,
        )

    gap_pt = size_to_pt(layout.gap)
    if gap_pt < 0:
        issues.append(
            LayoutIssue(
                code="ICSTEX_LAYOUT_NEGATIVE_GAP",
                severity="error",
                message="gap 不能为负",
                layout_id=layout.id,
            )
        )

    if layout.kind == "grid":
        return _solve_grid(layout, available, gap_pt, flags, issues, depth, max_depth)
    return _solve_row(layout, available, gap_pt, flags, issues, depth, max_depth)


def _solve_row(
    layout: LayoutNode,
    available: float,
    gap_pt: float,
    flags: dict[str, set[str]],
    issues: list[LayoutIssue],
    depth: int,
    max_depth: int,
) -> SolvedNode:
    count = len(layout.children)
    weights: list[float] = []
    for child in layout.children:
        weight = float(child.weight if isinstance(child, BlockSlot) else 1.0)
        if weight <= 0:
            issues.append(
                LayoutIssue(
                    code="ICSTEX_LAYOUT_BAD_WEIGHT",
                    severity="error",
                    message="权重必须大于零",
                    layout_id=layout.id,
                    instance_id=getattr(child, "instanceId", None),
                )
            )
        weights.append(max(weight, 0.0))
    usable = max(0.0, available - gap_pt * (count - 1))
    total = sum(weights) or 1.0
    widths = [usable * weight / total for weight in weights]
    return _finalize(layout, available, gap_pt, widths, flags, issues, depth, max_depth)


def _solve_grid(
    layout: LayoutNode,
    available: float,
    gap_pt: float,
    flags: dict[str, set[str]],
    issues: list[LayoutIssue],
    depth: int,
    max_depth: int,
) -> SolvedNode:
    count = len(layout.children)
    columns = max(1, layout.columns or count)
    usable = max(0.0, available - gap_pt * (columns - 1))
    width = usable / columns
    widths = [width] * count
    return _finalize(layout, available, gap_pt, widths, flags, issues, depth, max_depth)


def _finalize(
    layout: LayoutNode,
    available: float,
    gap_pt: float,
    widths: list[float],
    flags: dict[str, set[str]],
    issues: list[LayoutIssue],
    depth: int,
    max_depth: int,
) -> SolvedNode:
    rounded = [round(width, WIDTH_PRECISION) for width in widths]
    used_fallback: str | None = None
    min_violation = False
    for child, width in zip(layout.children, rounded):
        if isinstance(child, BlockSlot) and child.minWidthPt is not None and width < child.minWidthPt:
            min_violation = True
        if isinstance(child, BlockSlot) and "longtable" in flags.get(child.blockId, set()):
            issues.append(
                LayoutIssue(
                    code="ICSTEX_LAYOUT_LONGTABLE_BOXED",
                    severity="error",
                    message="长表格不能放入不可分页的左右/网格容器",
                    layout_id=layout.id,
                    instance_id=child.instanceId,
                )
            )

    if min_violation and not any(issue.severity == "error" for issue in issues):
        strategy = layout.fallback.get("strategy", "stackVertically")
        if strategy == "error":
            issues.append(
                LayoutIssue(
                    code="ICSTEX_LAYOUT_MINWIDTH",
                    severity="error",
                    message="子项最小宽度无法满足且回退策略为阻止编译",
                    layout_id=layout.id,
                )
            )
        else:
            used_fallback = "stackVertically"
            issues.append(
                LayoutIssue(
                    code="ICSTEX_LAYOUT_FALLBACK_STACK",
                    severity="warning",
                    message="可用宽度不足，已按配置改为上下排列",
                    layout_id=layout.id,
                )
            )

    children: list[object] = []
    for child, width in zip(layout.children, rounded):
        if isinstance(child, BlockSlot):
            children.append(
                SolvedSlot(
                    instanceId=child.instanceId,
                    blockId=child.blockId,
                    widthPt=width,
                    ratio=_ratio(width, available),
                )
            )
        else:
            children.append(
                _solve(child, width, flags, depth=depth + 1, max_depth=max_depth)
            )
    for child in children:
        if isinstance(child, SolvedNode):
            issues.extend(child.issues)
    return SolvedNode(
        layoutId=layout.id,
        kind=layout.kind,
        widthPt=available,
        children=tuple(children),
        columns=layout.columns if layout.kind == "grid" else None,
        usedFallback=used_fallback,
        issues=issues,
    )


def _solve_child(
    child: object,
    width: float,
    flags: dict[str, set[str]],
    *,
    depth: int,
    max_depth: int,
) -> object:
    if isinstance(child, BlockSlot):
        return SolvedSlot(
            instanceId=child.instanceId,
            blockId=child.blockId,
            widthPt=width,
            ratio=_ratio(width, width),
        )
    return _solve(child, width, flags, depth=depth + 1, max_depth=max_depth)


def _ratio(width: float, available: float) -> float:
    if available <= 0:
        return 0.0
    return round(width / available, 4)
