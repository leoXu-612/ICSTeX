from __future__ import annotations

from pathlib import Path
import sys


def asset_path(filename: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "app" / "assets" / filename
    return Path(__file__).resolve().parents[1] / "assets" / filename


def app_cover_path() -> Path:
    return asset_path("icstex_cover.png")
