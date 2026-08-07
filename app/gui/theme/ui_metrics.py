"""Unified UI design tokens derived from a single scale factor.

Every size in the UI derives from these tokens; nothing multiplies the
current font or current widget size by scale again (that would accumulate).
All values are design-baseline × ``scale`` (device-independent pixels; Qt 6
handles High DPI natively).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UiMetrics:
    scale: float = 1.0
    density: float = 1.0  # "comfortable" default; "compact" < 1.0

    # --- spacing ---------------------------------------------------------
    @property
    def spacing_xs(self) -> int:
        return round(4 * self.scale)

    @property
    def spacing_sm(self) -> int:
        return round(8 * self.scale * self.density)

    @property
    def spacing_md(self) -> int:
        return round(12 * self.scale * self.density)

    @property
    def spacing_lg(self) -> int:
        return round(20 * self.scale * self.density)

    @property
    def spacing_xl(self) -> int:
        return round(28 * self.scale * self.density)

    # --- controls --------------------------------------------------------
    @property
    def control_height(self) -> int:
        return round(34 * self.scale)

    @property
    def large_control_height(self) -> int:
        return round(44 * self.scale)

    @property
    def compact_control_height(self) -> int:
        return round(28 * self.scale)

    @property
    def panel_header_height(self) -> int:
        return round(38 * self.scale)

    @property
    def row_height(self) -> int:
        return round(26 * self.scale * self.density)

    # --- icons -----------------------------------------------------------
    @property
    def icon_size(self) -> int:
        return round(18 * self.scale)

    @property
    def toolbar_icon_size(self) -> int:
        return round(20 * self.scale)

    @property
    def large_icon_size(self) -> int:
        return round(28 * self.scale)

    @property
    def logo_size(self) -> int:
        return round(88 * self.scale)

    # --- radii -----------------------------------------------------------
    @property
    def corner_radius(self) -> int:
        return round(7 * self.scale)

    @property
    def card_radius(self) -> int:
        return round(12 * self.scale)

    # --- layout constraints ---------------------------------------------
    @property
    def dock_min_width(self) -> int:
        return round(230 * self.scale)

    @property
    def inspector_min_width(self) -> int:
        return round(300 * self.scale)

    @property
    def diagnostics_default_height(self) -> int:
        return round(200 * self.scale)


# Font roles: base point sizes that scale with ui scale, never accumulated.
@dataclass(frozen=True)
class TypographyMetrics:
    scale: float = 1.0

    @property
    def body_pt(self) -> float:
        return 13.0 * self.scale

    @property
    def caption_pt(self) -> float:
        return 11.0 * self.scale

    @property
    def button_pt(self) -> float:
        return 13.0 * self.scale

    @property
    def toolbar_pt(self) -> float:
        return 12.0 * self.scale

    @property
    def section_title_pt(self) -> float:
        return 12.0 * self.scale

    @property
    def page_title_pt(self) -> float:
        return 23.0 * self.scale

    @property
    def monospace_pt(self) -> float:
        return 13.0 * self.scale
