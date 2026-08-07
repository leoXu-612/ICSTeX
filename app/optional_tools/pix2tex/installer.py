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
    """Download pix2tex weights once (upstream package checkpoints dir)."""
    code = (
        "import json\n"
        "import pathlib\n"
        "from pix2tex import cli as _cli\n"
        "import inspect\n"
        "import os\n"
        "from pix2tex.cli import LatexOCR\n"
        "pkg = pathlib.Path(inspect.getfile(LatexOCR)).parent\n"
        "LatexOCR()\n"
        "ckpt = pkg / 'model' / 'checkpoints'\n"
        "manifest = {\n"
        "  'version': 'pix2tex-0.1.4',\n"
        "  'checkpoint': str(ckpt / 'weights.pth'),\n"
        "  'image_resizer': str(ckpt / 'image_resizer.pth'),\n"
        "  'tokenizer': str(pkg / 'model' / 'settings' / 'tokenizer.json'),\n"
        "  'config': str(pkg / 'model' / 'settings' / 'config.yaml'),\n"
        "}\n"
        "print(json.dumps(manifest))\n"
    )
    try:
        result = subprocess.run(
            [str(python_executable()), "-c", code],
            check=False,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": "model download timed out"}
    if result.returncode != 0:
        return {"ok": False, "detail": (result.stderr or result.stdout)[-500:]}
    import json as _json

    manifest = _json.loads(result.stdout.strip().splitlines()[-1])
    manifest_path().write_text(_json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "status": status()}
