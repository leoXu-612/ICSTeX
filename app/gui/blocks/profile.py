"""Block compile pipeline transaction profiler.

Enabled only when ``ICSTEX_COMPILE_PROFILE=1``; production consoles see no
output.  Emits one line per event with a transaction id and revision so the
audit can reconstruct the full edit -> PDF timeline.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from itertools import count


ENABLED = os.environ.get("ICSTEX_COMPILE_PROFILE") == "1"
_REVISIONS = count(1)
_lock = threading.Lock()
_started = time.perf_counter()


def new_revision() -> int:
    return next(_REVISIONS)


def log(event: str, **fields) -> None:
    if not ENABLED:
        return
    parts = [f"t+{(time.perf_counter() - _started) * 1000:9.1f}ms", f"event={event}"]
    parts.extend(f"{key}={value}" for key, value in fields.items() if value is not None)
    with _lock:
        print("block-perf: " + " ".join(parts), file=sys.stderr)


class Stopwatch:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000.0
