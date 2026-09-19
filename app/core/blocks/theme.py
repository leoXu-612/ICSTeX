"""App and document theme models (Sprint 5).

The two themes are fully separated: the app theme controls the software UI
and never reaches LaTeX; the document theme controls the final PDF and is
rendered to a ``.sty`` file. Token completeness is validated at load time.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.blocks.model import SCHEMA_VERSION


APP_THEME_TOKENS: tuple[str, ...] = (
    "background",
    "surface",
    "surfaceElevated",
    "foreground",
    "foregroundMuted",
    "border",
    "accent",
    "accentForeground",
    "selection",
    "success",
    "warning",
    "error",
    "layoutGuide",
)


@dataclass
class AppTheme:
    schemaVersion: str = SCHEMA_VERSION
    kind: str = "app-theme"
    id: str = ""
    name: str = ""
    mode: str = "light"
    tokens: dict = field(default_factory=dict)
    typography: dict = field(default_factory=dict)
    effects: dict = field(default_factory=dict)

    def missing_tokens(self) -> list[str]:
        return [token for token in APP_THEME_TOKENS if token not in self.tokens]

    def to_dict(self) -> dict:
        return {
            "schemaVersion": self.schemaVersion,
            "kind": self.kind,
            "id": self.id,
            "name": self.name,
            "mode": self.mode,
            "tokens": self.tokens,
            "typography": self.typography,
            "effects": self.effects,
        }


@dataclass
class DocumentTheme:
    schemaVersion: str = SCHEMA_VERSION
    kind: str = "document-theme"
    id: str = ""
    name: str = ""
    page: dict = field(default_factory=dict)
    typography: dict = field(default_factory=dict)
    headings: dict = field(default_factory=dict)
    figures: dict = field(default_factory=dict)
    tables: dict = field(default_factory=dict)
    layout: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schemaVersion": self.schemaVersion,
            "kind": self.kind,
            "id": self.id,
            "name": self.name,
            "page": self.page,
            "typography": self.typography,
            "headings": self.headings,
            "figures": self.figures,
            "tables": self.tables,
            "layout": self.layout,
        }


def theme_from_dict(data: dict) -> AppTheme | DocumentTheme:
    if data.get("kind") == "app-theme":
        return AppTheme(
            schemaVersion=data.get("schemaVersion", SCHEMA_VERSION),
            id=data.get("id", ""),
            name=data.get("name", ""),
            mode=data.get("mode", "light"),
            tokens=dict(data.get("tokens", {})),
            typography=dict(data.get("typography", {})),
            effects=dict(data.get("effects", {})),
        )
    return DocumentTheme(
        schemaVersion=data.get("schemaVersion", SCHEMA_VERSION),
        id=data.get("id", ""),
        name=data.get("name", ""),
        page=dict(data.get("page", {})),
        typography=dict(data.get("typography", {})),
        headings=dict(data.get("headings", {})),
        figures=dict(data.get("figures", {})),
        tables=dict(data.get("tables", {})),
        layout=dict(data.get("layout", {})),
    )
