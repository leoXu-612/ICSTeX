"""Layout tree model (Sprint 2): Row/Column/Grid/FullWidth over Block IDs.

Layouts never copy Block content; they reference Blocks by stable ID through
BlockSlots. Width, gap, alignment, and fallback rules live on the layout only.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.blocks.model import SCHEMA_VERSION


LAYOUT_KINDS: tuple[str, ...] = ("row", "column", "grid", "fullWidth")
FALLBACK_STRATEGIES: tuple[str, ...] = (
    "reduceGap",
    "normalizeWeights",
    "wrapRows",
    "stackVertically",
    "error",
)


@dataclass(frozen=True)
class Size:
    value: float
    unit: str = "mm"


@dataclass(frozen=True)
class BlockSlot:
    instanceId: str
    blockId: str
    weight: float = 1.0
    minWidthPt: float | None = None

    def to_dict(self) -> dict:
        return {
            "instanceId": self.instanceId,
            "kind": "block",
            "blockId": self.blockId,
            "weight": self.weight,
            "minWidthPt": self.minWidthPt,
        }


@dataclass(frozen=True)
class LayoutNode:
    schemaVersion: str = SCHEMA_VERSION
    id: str = ""
    kind: str = "row"
    children: tuple[object, ...] = ()
    columns: int | None = None
    gap: Size | None = None
    rowGap: Size | None = None
    alignment: str = "top"
    keepTogether: str = "row"
    fallback: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        result: dict = {
            "schemaVersion": self.schemaVersion,
            "id": self.id,
            "kind": self.kind,
            "alignment": self.alignment,
            "keepTogether": self.keepTogether,
            "fallback": self.fallback,
            "children": [child.to_dict() for child in self.children],
        }
        if self.columns is not None:
            result["columns"] = self.columns
        if self.gap is not None:
            result["gap"] = {"value": self.gap.value, "unit": self.gap.unit}
        if self.rowGap is not None:
            result["rowGap"] = {"value": self.rowGap.value, "unit": self.rowGap.unit}
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "LayoutNode":
        children: list[object] = []
        for raw in data.get("children", []):
            if raw.get("kind") == "block":
                children.append(
                    BlockSlot(
                        instanceId=raw["instanceId"],
                        blockId=raw["blockId"],
                        weight=float(raw.get("weight", 1.0)),
                        minWidthPt=raw.get("minWidthPt"),
                    )
                )
            else:
                children.append(cls.from_dict(raw))
        gap = data.get("gap")
        row_gap = data.get("rowGap")
        return cls(
            schemaVersion=data.get("schemaVersion", SCHEMA_VERSION),
            id=data.get("id", ""),
            kind=data.get("kind", "row"),
            children=tuple(children),
            columns=data.get("columns"),
            gap=Size(value=float(gap["value"]), unit=gap.get("unit", "mm")) if gap else None,
            rowGap=Size(value=float(row_gap["value"]), unit=row_gap.get("unit", "mm")) if row_gap else None,
            alignment=data.get("alignment", "top"),
            keepTogether=data.get("keepTogether", "row"),
            fallback=dict(data.get("fallback", {})),
        )


def block_slot(block_id: str, *, weight: float = 1.0, min_width_pt: float | None = None) -> BlockSlot:
    from app.core.blocks.ids import new_instance_id

    return BlockSlot(
        instanceId=new_instance_id(),
        blockId=block_id,
        weight=weight,
        minWidthPt=min_width_pt,
    )
