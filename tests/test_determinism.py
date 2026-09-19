from __future__ import annotations

from unittest import TestCase

from app.core.blocks.block_renderer import render_block
from app.core.blocks.formula_adapter import FormulaBlockAdapter
from app.core.blocks.layout import BlockSlot, LayoutNode, Size
from app.core.blocks.layout_renderer import render_layout
from app.core.blocks.layout_solver import solve_layout
from app.core.blocks.model import Block, Semantic, content_for_text


class DeterminismSuiteTests(TestCase):
    def test_same_model_renders_identically_three_times(self) -> None:
        blocks = {
            "blk_a": Block(id="blk_a", type="text", alias="a", semantic=Semantic(role="text"), content=content_for_text("结果分析")),
            "blk_b": Block(
                id="blk_b",
                type="formula",
                alias="b",
                semantic=Semantic(role="equation", label="eq:x"),
                content=FormulaBlockAdapter().content_for(r"r = k[A]"),
            ),
        }
        layout = LayoutNode(
            id="lyt_deterministic",
            kind="row",
            gap=Size(value=8, unit="mm"),
            fallback={"strategy": "stackVertically"},
            children=(
                BlockSlot(instanceId="ins_a", blockId="blk_a", weight=1, minWidthPt=100),
                BlockSlot(instanceId="ins_b", blockId="blk_b", weight=1, minWidthPt=100),
            ),
        )
        block_latex = {block_id: render_block(block, in_box=True) for block_id, block in blocks.items()}

        outputs = [
            render_layout(solve_layout(layout, 426.0), block_latex) for _ in range(3)
        ]

        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])
