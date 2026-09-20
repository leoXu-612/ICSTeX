"""Deterministic fake OCR worker for tests and GUI development without models.

Speaks the same JSON Lines protocol as worker_entry but never imports
pix2tex.  Behavior can be driven via environment flags to simulate loading,
results, errors, hangs and crashes.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from app.optional_tools.pix2tex.protocol import encode_message


def main() -> int:
    mode = os.environ.get("ICSTEX_FAKE_OCR_MODE", "ok")
    if mode == "crash":
        return 9
    if mode == "invalid_json":
        sys.stdout.write("{not json\n")
        sys.stdout.flush()
        return 0
    if mode == "hang":
        time.sleep(600)
        return 0

    sys.stdout.write(encode_message({"event": "loading_model"}))
    sys.stdout.flush()
    time.sleep(0.05)
    if mode == "load_fail":
        sys.stdout.write(
            encode_message({"event": "error", "error": {"code": "MODEL_LOAD_FAILED", "message": "fake"}})
        )
        sys.stdout.flush()
        return 4
    sys.stdout.write(encode_message({"event": "ready", "model_version": "fake-1.0"}))
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(encode_message({"id": None, "error": {"code": "BAD_REQUEST", "message": "bad"}}))
            sys.stdout.flush()
            continue
        request_id = message.get("id")
        if message.get("method") == "shutdown":
            sys.stdout.write(encode_message({"id": request_id, "event": "shutdown"}))
            sys.stdout.flush()
            return 0
        if mode == "slow":
            time.sleep(5)
        path = Path(message.get("params", {}).get("image_path", ""))
        sys.stdout.write(
            encode_message(
                {
                    "id": request_id,
                    "result": {
                        "latex": r"\frac{x^2+1}{\sqrt{y}}",
                        "elapsed_ms": 12,
                        "model_version": "fake-1.0",
                        "source_image_size": [32, 32],
                    },
                }
            )
        )
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
