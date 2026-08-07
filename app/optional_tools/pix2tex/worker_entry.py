"""pix2tex sidecar worker (runs inside the isolated venv).

JSON Lines on stdin/stdout only; third-party logs go to stderr.  Model files
must already exist (no auto download); clipboard side-effects are disabled.
pix2tex is imported lazily so the core app never imports it.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from app.optional_tools.pix2tex.manifest import load_manifest
from app.optional_tools.pix2tex.protocol import encode_message


def _emit(payload: dict) -> None:
    sys.stdout.write(encode_message(payload))
    sys.stdout.flush()


def _noop_clipboard_copy(_text: str) -> None:
    return None


def _disable_clipboard_side_effects() -> None:
    """Upstream may copy the result to the clipboard; block that."""
    try:
        import pix2tex.cli as cli
    except Exception:  # noqa: BLE001 - import location varies
        return
    for module_name in ("pyperclip", "sublime"):
        module = getattr(cli, module_name, None)
        if module is not None and hasattr(module, "copy"):
            try:
                module.copy = _noop_clipboard_copy
            except Exception:  # noqa: BLE001
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--temperature", type=float, default=0.01)
    parser.add_argument("--use-resizer", action="store_true", default=True)
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    missing = manifest.missing_files()
    if missing:
        _emit({"event": "error", "error": {"code": "MODEL_MISSING", "message": "model files missing"}})
        return 2

    try:
        import pix2tex.cli  # noqa: F401 - import inside the venv only
    except Exception as exc:  # noqa: BLE001
        _emit({"event": "error", "error": {"code": "IMPORT_FAILED", "message": str(exc)}})
        return 3

    _disable_clipboard_side_effects()
    _emit({"event": "loading_model"})
    try:
        from munch import Munch
        from pix2tex.cli import LatexOCR

        arguments = Munch(
            {
                "config": str(manifest.config),
                "checkpoint": str(manifest.checkpoint),
                "no_cuda": True,
                "no_resize": not args.use_resizer,
                "temperature": args.temperature,
            }
        )
        model = LatexOCR(arguments=arguments)
    except Exception as exc:  # noqa: BLE001
        _emit({"event": "error", "error": {"code": "MODEL_LOAD_FAILED", "message": str(exc)}})
        return 4
    _emit({"event": "ready", "model_version": manifest.version})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            _emit({"id": None, "error": {"code": "BAD_REQUEST", "message": "invalid json"}})
            continue
        method = message.get("method")
        request_id = message.get("id")
        if method == "shutdown":
            _emit({"id": request_id, "event": "shutdown"})
            return 0
        if method != "recognize":
            _emit({"id": request_id, "error": {"code": "UNKNOWN_METHOD", "message": method or ""}})
            continue
        params = message.get("params", {})
        image_path = Path(params.get("image_path", ""))
        if not image_path.is_file():
            _emit({"id": request_id, "error": {"code": "IMAGE_MISSING", "message": str(image_path)}})
            continue
        _emit({"id": request_id, "event": "inference_started"})
        started = time.perf_counter()
        try:
            from PIL import Image

            image = Image.open(image_path).convert("RGB")
            latex = model(image)
        except Exception as exc:  # noqa: BLE001
            _emit({"id": request_id, "error": {"code": "INFERENCE_FAILED", "message": str(exc)}})
            continue
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        _emit(
            {
                "id": request_id,
                "result": {
                    "latex": str(latex),
                    "elapsed_ms": elapsed_ms,
                    "model_version": manifest.version,
                },
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
