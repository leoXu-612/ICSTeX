"""Install/remove/status for the isolated pix2tex venv and models."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import venv

from app.optional_tools.pix2tex.environment import PIX2TEX_PIN, manifest_path, models_dir, pix2tex_root, python_executable, state_path, venv_dir


def status() -> dict:
    installed = python_executable().exists()
    state = {}
    if state_path().is_file():
        try:
            state = json.loads(state_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
    models_ready = manifest_path().is_file()
    return {
        "installed": installed,
        "models_ready": models_ready,
        "python": str(python_executable()) if installed else None,
        "state": state,
    }


def install(python: str | None = None, *, timeout: int = 900) -> dict:
    """Create the venv and install the pinned pix2tex base package."""
    base_python = python or sys.executable
    if not python_executable().exists():
        venv.EnvBuilder(with_pip=True, clear=False).create(str(venv_dir()))
    exe = str(python_executable())
    subprocess.run(
        [exe, "-m", "pip", "install", "--upgrade", "pip"],
        check=False,
        timeout=timeout,
    )
    subprocess.run(
        [exe, "-m", "pip", "install", f"pix2tex=={PIX2TEX_PIN}"],
        check=True,
        timeout=timeout,
        capture_output=True,
    )
    models_dir().mkdir(parents=True, exist_ok=True)
    payload = {"installed": True, "pin": PIX2TEX_PIN, "python": exe}
    state_path().parent.mkdir(parents=True, exist_ok=True)
    state_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return status()


def remove() -> None:
    if pix2tex_root().exists():
        shutil.rmtree(pix2tex_root())


def download_models(timeout: int = 900) -> dict:
    """One-shot model download into models_dir; writes the manifest.

    Runs inside the venv with explicit config/checkpoint paths so upstream
    downloads the weights exactly once into the optional tool directory.
    """
    code = (
        "import json, pathlib\n"
        "from pix2tex.cli import LatexOCR\n"
        "root = pathlib.Path(__import__('app.optional_tools.pix2tex.environment', fromlist=['models_dir']).models_dir())\n"
        "root.mkdir(parents=True, exist_ok=True)\n"
        "config = root / 'config.yaml'\n"
        "checkpoint = root / 'weights.pth'\n"
        "LatexOCR(config=str(config), checkpoint=str(checkpoint), no_cuda=True)\n"
        "manifest = {'version': 'pix2tex-0.1.4', 'checkpoint': 'weights.pth', "
        "'image_resizer': 'image_resizer.pth', 'tokenizer': 'tokenizer.json', 'config': 'config.yaml'}\n"
        "(root / 'model-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')\n"
    )
    result = subprocess.run(
        [str(python_executable()), "-c", code],
        check=False,
        timeout=timeout,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {"ok": False, "detail": (result.stderr or result.stdout)[-500:]}
    return {"ok": True, "status": status()}
