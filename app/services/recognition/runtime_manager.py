"""Local recognition runtime: detect/install/remove/manifest/disk + pip index."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


PYPi_URL = "https://pypi.org/simple"
PIX2TEX_PIN = "0.1.4"
RAPIDOCR_PACKAGE = "rapidocr_onnxruntime"


def provider_venv_root(provider: str) -> Path:
    override = os.environ.get("ICSTEX_PIX2TEX_ENV" if provider == "pix2tex" else "ICSTEX_RAPIDOCR_ENV")
    if override:
        return Path(override).expanduser()
    from PySide6.QtCore import QStandardPaths

    base = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    return base / "optional-tools" / provider


def provider_python(provider: str) -> Path:
    root = provider_venv_root(provider)
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def installed(provider: str) -> bool:
    return provider_python(provider).exists()


def read_manifest(provider: str) -> dict:
    path = provider_venv_root(provider) / "models" / "model-manifest.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def disk_usage(provider: str) -> int:
    root = provider_venv_root(provider)
    if not root.exists():
        return 0
    total = 0
    for path in root.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                pass
    return total


def pip_index(python: str | Path | None = None) -> str | None:
    """Return the configured pip index-url (None when not set or official)."""
    executable = str(python or sys.executable)
    try:
        result = subprocess.run(
            [executable, "-m", "pip", "config", "list"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in result.stdout.splitlines():
        if line.strip().startswith("global.index-url="):
            value = line.split("=", 1)[1].strip()
            return value if "pypi.org" not in value else None
    return None


def install_commands(provider: str) -> list[list[str]]:
    """Return the pip install commands (official PyPI forced per-process)."""
    python = str(provider_python(provider))
    if provider == "pix2tex":
        return [[python, "-m", "pip", "install", "--index-url", PYPi_URL, f"pix2tex=={PIX2TEX_PIN}"]]
    return [[python, "-m", "pip", "install", "--index-url", PYPi_URL, RAPIDOCR_PACKAGE]]


def remove(provider: str) -> bool:
    root = provider_venv_root(provider)
    if not root.exists():
        return False
    shutil.rmtree(root)
    return True


def detect() -> dict:
    return {
        "pix2tex": {"installed": installed("pix2tex"), "manifest": bool(read_manifest("pix2tex"))},
        "rapidocr": {"installed": installed("rapidocr"), "manifest": bool(read_manifest("rapidocr"))},
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
    }
