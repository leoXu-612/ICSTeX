"""Optional tool paths (portable; resolved from QStandardPaths at runtime)."""
from __future__ import annotations

import sys
import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths


PIX2TEX_PIN = "0.1.4"


def optional_tools_root() -> Path:
    base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    return base / "optional-tools"


def pix2tex_root() -> Path:
    return optional_tools_root() / "pix2tex"


def venv_dir() -> Path:
    return pix2tex_root() / "venv"


def python_executable() -> Path:
    override = os.environ.get("ICSTEX_PIX2TEX_ENV")
    if override:
        root = Path(override).expanduser()
        if sys.platform == "win32":
            return root / "Scripts" / "python.exe"
        return root / "bin" / "python"
    if sys.platform == "win32":
        return venv_dir() / "Scripts" / "python.exe"
    return venv_dir() / "bin" / "python"


def models_dir() -> Path:
    return pix2tex_root() / "models"


def manifest_path() -> Path:
    return models_dir() / "model-manifest.json"


def state_path() -> Path:
    return pix2tex_root() / "state.json"


def logs_dir() -> Path:
    return pix2tex_root() / "logs"


def licenses_dir() -> Path:
    return pix2tex_root() / "licenses"
