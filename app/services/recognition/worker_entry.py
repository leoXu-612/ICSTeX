"""Generic local recognition worker (JSON Lines; lazy provider load).

Protocol v1: stdin requests / stdout responses, stderr for logs.  Formula
uses pix2tex; text uses RapidOCR.  Providers import lazily so a worker that
only ever runs one kind never loads the other's dependencies.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def _load_image(path: Path):
    from PIL import Image

    image = Image.open(path)
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        white = Image.new("RGBA", image.size, "white")
        image = Image.alpha_composite(white, image.convert("RGBA")).convert("RGB")
    else:
        image = image.convert("RGB")
    return image


def _formula_latex(image_path: Path, manifest: dict, temperature: float) -> str:
    import inspect

    from munch import Munch
    from pix2tex.cli import LatexOCR

    pkg = Path(inspect.getfile(LatexOCR)).parent
    arguments = Munch(
        {
            "config": manifest.get("config") or str(pkg / "model" / "settings" / "config.yaml"),
            "checkpoint": manifest.get("checkpoint") or str(pkg / "model" / "checkpoints" / "weights.pth"),
            "no_cuda": True,
            "no_resize": False,
            "temperature": temperature,
        }
    )
    model = LatexOCR(arguments=arguments)
    return str(model(_load_image(image_path)))


def _text_regions(image_path: Path) -> list[dict]:
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    result, _elapsed = engine(str(image_path))
    regions: list[dict] = []
    for item in result or []:
        box, text, confidence = item[0], item[1], float(item[2])
        regions.append({"text": str(text), "confidence": confidence, "box": box})
    return regions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("formula", "text"))
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--temperature", type=float, default=0.01)
    args = parser.parse_args(argv)
    manifest: dict = {}
    if args.manifest is not None and args.manifest.is_file():
        try:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = {}

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            _emit({"ok": False, "error": {"code": "BAD_REQUEST", "message": "invalid json"}})
            continue
        request_id = message.get("requestId")
        action = message.get("action")
        if action == "shutdown":
            _emit({"ok": True, "requestId": request_id, "action": "shutdown"})
            return 0
        if action == "health":
            _emit({"ok": True, "requestId": request_id, "action": "health", "provider": args.kind})
            continue
        if action != "recognize":
            _emit({"ok": False, "requestId": request_id, "error": {"code": "UNKNOWN_ACTION", "message": action or ""}})
            continue
        kind = message.get("kind") or args.kind
        image_path = Path(message.get("imagePath", ""))
        if not image_path.is_file():
            _emit({"ok": False, "requestId": request_id, "error": {"code": "IMAGE_MISSING", "message": str(image_path)}})
            continue
        started = time.perf_counter()
        try:
            if kind == "formula":
                latex = _formula_latex(image_path, manifest, float(message.get("temperature", args.temperature)))
                payload = {"ok": True, "requestId": request_id, "kind": "formula", "provider": "pix2tex", "latex": latex}
            else:
                regions = _text_regions(image_path)
                text = "\n".join(region["text"] for region in regions)
                payload = {"ok": True, "requestId": request_id, "kind": "text", "provider": "rapidocr", "text": text, "regions": regions}
        except Exception as exc:  # noqa: BLE001
            _emit({"ok": False, "requestId": request_id, "error": {"code": "INFERENCE_FAILED", "message": str(exc)}})
            continue
        payload["elapsedMs"] = int((time.perf_counter() - started) * 1000)
        _emit(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
