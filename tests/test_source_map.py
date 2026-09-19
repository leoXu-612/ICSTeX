from __future__ import annotations

from unittest import TestCase

from app.core.blocks.block_renderer import render_block
from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.layout import LayoutNode, block_slot
from app.core.blocks.layout_renderer import render_layout
from app.core.blocks.layout_solver import solve_layout
from app.core.blocks.model import Block, Semantic, content_for_text
from app.core.blocks.source_map import block_at_line, build_source_map


class SourceMapTests(TestCase):
    def test_build_map_tracks_block_ranges(self) -> None:
        first = Block(id="blk_a", type="text", alias="a", semantic=Semantic(role="text"), content=content_for_text("第一段"))
        second = Block(
            id="blk_b",
            type="formula",
            alias="b",
            semantic=Semantic(role="equation"),
            content=FormulaBlockAdapter().content_for(r"E=mc^2"),
        )
        latex = render_block(first) + render_block(second)
        source_map = build_source_map(latex)

        self.assertIn("blk_a", source_map)
        self.assertIn("blk_b", source_map)
        self.assertGreater(source_map["blk_b"]["start_line"], source_map["blk_a"]["end_line"])
        self.assertLessEqual(source_map["blk_a"]["start_line"], source_map["blk_a"]["end_line"])

    def test_block_at_line_attribution(self) -> None:
        block = Block(id="blk_t", type="text", alias="t", semantic=Semantic(role="text"), content=content_for_text("定位测试"))
        latex = render_block(block)
        lines = latex.splitlines()
        middle = lines.index(next(line for line in lines if "定位测试" in line)) + 1

        found = block_at_line(latex, middle)
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found["blockId"], "blk_t")
        self.assertIsNone(block_at_line(latex, 999))

    def test_layout_slot_attribution_in_row(self) -> None:
        first = Block(id="blk_a", type="text", alias="a", semantic=Semantic(role="text"), content=content_for_text("A"))
        second = Block(id="blk_b", type="text", alias="b", semantic=Semantic(role="text"), content=content_for_text("B"))
        layout = LayoutNode(
            id="lyt_row",
            kind="row",
            children=(block_slot("blk_a"), block_slot("blk_b")),
        )
        latex = render_layout(
            solve_layout(layout, 300.0),
            {"blk_a": render_block(first), "blk_b": render_block(second)},
        )
        source_map = build_source_map(latex)

        self.assertEqual(source_map["blk_a"]["layout_id"], "lyt_row")
        self.assertIsNotNone(source_map["blk_a"]["slot_instance_id"])
