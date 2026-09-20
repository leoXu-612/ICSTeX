"""Deterministic fake worker for tests and GUI dev (no models)."""
from __future__ import annotations

import json
import os
import sys
import time


def main() -> int:
    if os.environ.get("ICSTEX_FAKE_OCR_MODE") == "crash":
        return 9
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        message = json.loads(line)
        request_id = message.get("requestId")
        action = message.get("action")
        if action == "shutdown":
            print(json.dumps({"ok": True, "requestId": request_id, "action": "shutdown"}))
            sys.stdout.flush()
            return 0
        if action == "health":
            print(json.dumps({"ok": True, "requestId": request_id, "action": "health", "provider": message.get("kind")}))
            sys.stdout.flush()
            continue
        if action == "recognize":
            kind = message.get("kind")
            if kind == "formula":
                payload = {"ok": True, "requestId": request_id, "kind": "formula", "provider": "pix2tex", "latex": r"\frac{x^2+1}{\sqrt{y}}"}
            else:
                payload = {"ok": True, "requestId": request_id, "kind": "text", "provider": "rapidocr", "text": "Experimental Results", "regions": [{"text": "Experimental Results", "confidence": 0.99, "box": [[7, 20], [304, 20], [304, 60], [7, 60]]}]}
            payload["elapsedMs"] = 5
            print(json.dumps(payload))
            sys.stdout.flush()
            continue
        print(json.dumps({"ok": False, "requestId": request_id, "error": {"code": "UNKNOWN_ACTION", "message": action or ""}}))
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
