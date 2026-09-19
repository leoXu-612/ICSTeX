from __future__ import annotations

from unittest import TestCase

from app.core.blocks.ids import new_instance_id
from app.core.blocks.layout import BlockSlot, LayoutNode, Size, block_slot
from app.core.blocks.layout_solver import (
    LayoutIssue,
    solve_layout,
)
from app.core.blocks.schema import validate_layout


def row_with_slots(slots: list[BlockSlot], **overrides: object) -> LayoutNode:
    return LayoutNode(
        id="lyt_row",
        kind="row",
        gap=Size(value=8, unit="mm"),
        children=tuple(slots),
        **overrides,
    )


class LayoutModelTests(TestCase):
    def test_serialize_round_trip(self) -> None:
        node = LayoutNode(
            id="lyt_grid",
            kind="grid",
            columns=2,
            gap=Size(value=6, unit="mm"),
            fallback={"strategy": "stackVertically", "minimumChildWidthPt": 120},
            children=(
                block_slot("blk_a", weight=1, min_width_pt=100),
                block_slot("blk_b", weight=2),
            ),
        )
        restored = LayoutNode.from_dict(node.to_dict())
        self.assertEqual(restored.id, node.id)
        self.assertEqual(restored.children[0].blockId, "blk_a")
        self.assertEqual(restored.children[1].weight, 2.0)
        self.assertEqual(validate_layout(node.to_dict()), [])

    def test_schema_rejects_invalid_layouts(self) -> None:
        valid = row_with_slots([block_slot("blk_a")]).to_dict()
        self.assertEqual(validate_layout(valid), [])

        bad_kind = dict(valid, kind="video")
        self.assertTrue(validate_layout(bad_kind))

        bad_weight = dict(valid)
        bad_weight["children"] = [
            {"instanceId": new_instance_id(), "kind": "block", "blockId": "blk_a", "weight": 0}
        ]
        self.assertTrue(validate_layout(bad_weight))

        bad_gap = dict(valid, gap={"value": -1, "unit": "mm"})
        self.assertTrue(validate_layout(bad_gap))

        bad_strategy = dict(valid, fallback={"strategy": "stack"})
        self.assertTrue(validate_layout(bad_strategy))


class LayoutSolverTests(TestCase):
    def test_row_weights_subtract_gaps(self) -> None:
        slots = [block_slot("blk_a", weight=2), block_slot("blk_b", weight=3)]
        solved = solve_layout(row_with_slots(slots), 300.0)

        self.assertEqual([child.widthPt for child in solved.children], [110.895, 166.343])
        self.assertAlmostEqual(sum(child.widthPt for child in solved.children), 300.0 - 8 * 72.27 / 25.4, places=2)

    def test_grid_columns_equal_widths(self) -> None:
        slots = [block_slot(f"blk_{index}") for index in range(4)]
        layout = LayoutNode(id="lyt_grid", kind="grid", columns=2, gap=Size(value=8, unit="mm"), children=tuple(slots))
        solved = solve_layout(layout, 400.0)

        self.assertEqual(solved.columns, 2)
        self.assertEqual(len(solved.children), 4)
        self.assertAlmostEqual(solved.children[0].widthPt, (400.0 - 8 * 72.27 / 25.4) / 2, places=2)

    def test_min_width_triggers_stack_fallback(self) -> None:
        slots = [block_slot("blk_a", min_width_pt=200), block_slot("blk_b")]
        solved = solve_layout(row_with_slots(slots), 300.0)

        self.assertEqual(solved.usedFallback, "stackVertically")
        self.assertTrue(any(issue.code == "ICSTEX_LAYOUT_FALLBACK_STACK" for issue in solved.issues))

    def test_error_fallback_strategy_blocks_compile(self) -> None:
        slots = [block_slot("blk_a", min_width_pt=200), block_slot("blk_b")]
        layout = row_with_slots(slots, fallback={"strategy": "error"})
        solved = solve_layout(layout, 300.0)

        self.assertTrue(any(issue.code == "ICSTEX_LAYOUT_MINWIDTH" for issue in solved.issues))

    def test_longtable_flag_in_row_is_error(self) -> None:
        slots = [block_slot("blk_longtable"), block_slot("blk_image")]
        solved = solve_layout(row_with_slots(slots), 300.0, block_flags={"blk_longtable": {"longtable"}})

        self.assertTrue(any(issue.code == "ICSTEX_LAYOUT_LONGTABLE_BOXED" for issue in solved.issues))

    def test_empty_layout_is_error(self) -> None:
        solved = solve_layout(LayoutNode(id="lyt_empty", kind="row"), 300.0)
        self.assertTrue(any(issue.code == "ICSTEX_LAYOUT_EMPTY" for issue in solved.issues))

    def test_negative_gap_is_error(self) -> None:
        layout = LayoutNode(id="lyt_gap", kind="row", gap=Size(value=-1, unit="mm"), children=(block_slot("blk_a"),))
        solved = solve_layout(layout, 300.0)
        self.assertTrue(any(issue.code == "ICSTEX_LAYOUT_NEGATIVE_GAP" for issue in solved.issues))

    def test_nesting_depth_limit(self) -> None:
        child: object = block_slot("blk_a")
        for index in range(12):
            child = LayoutNode(
                id=f"lyt_deep_{index}",
                kind="row",
                children=(child,),
            )
        solved = solve_layout(child, 300.0)  # type: ignore[arg-type]
        self.assertTrue(any(issue.code == "ICSTEX_LAYOUT_DEPTH" for issue in solved.issues))

    def test_solve_does_not_mutate_blocks(self) -> None:
        slots = [block_slot("blk_a", weight=1), block_slot("blk_b", weight=1)]
        layout = row_with_slots(slots)
        layout_before = layout.to_dict()

        solve_layout(layout, 300.0)

        self.assertEqual(layout.to_dict(), layout_before)
