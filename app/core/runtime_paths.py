from __future__ import annotations

import os
import shutil
import sys


MACOS_EXTRA_TOOL_PATHS = (
    "/Library/TeX/texbin",
    "/usr/local/bin",
    "/opt/homebrew/bin",
    "/usr/texbin",
)


def augmented_path(base_path: str | None = None, *, platform: str | None = None) -> str:
    current_platform = platform or sys.platform
    path = base_path if base_path is not None else os.environ.get("PATH", "")
    parts = [part for part in path.split(os.pathsep) if part]
    if current_platform == "darwin":
        for extra_path in MACOS_EXTRA_TOOL_PATHS:
            if extra_path not in parts:
                parts.append(extra_path)
    return os.pathsep.join(parts)


def which_tool(name: str) -> str | None:
    return shutil.which(name, path=augmented_path())
