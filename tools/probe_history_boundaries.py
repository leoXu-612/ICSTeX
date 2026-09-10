"""Read-only-to-real-data orientation of legacy history, using disposable files.

Exit zero means the observations were recorded, NOT that legacy history is safe.
Do not use this as a regression acceptance test after the legacy path is repaired.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.core.history import create_snapshot, read_snapshot


def run(output):
    output = output.expanduser().absolute()
    output.mkdir(parents=False, exist_ok=False)
    project = output / "synthetic-project"
    project.mkdir()
    source = project / "main.tex"
    source.write_text("original source", encoding="utf-8")
    snapshot = create_snapshot(source, "first history entry", "synthetic")
    snapshot.snapshot_path.write_text("changed without updating digest", encoding="utf-8")
    try:
        read = read_snapshot(snapshot)
        hash_mismatch_accepted = hashlib.sha256(read.encode()).hexdigest() != snapshot.sha256
    except (OSError, ValueError):
        hash_mismatch_accepted = False
    sentinel = output / "outside-project-sentinel.tex"
    sentinel.write_text("first history entry", encoding="utf-8")
    manifest_path = snapshot.snapshot_path.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    forged = {**manifest[0], "snapshot_path": str(sentinel),
              "sha256": hashlib.sha256(sentinel.read_bytes()).hexdigest()}
    manifest_path.write_text(json.dumps([forged, *manifest]), encoding="utf-8")
    refused = False
    try:
        create_snapshot(source, "second history entry", "synthetic", max_snapshots=1)
    except (OSError, ValueError):
        refused = True
    report = {
        "boundary": "synthetic temporary data only; orientation, not acceptance",
        "legacy_history_py_sha256": hashlib.sha256((REPO / "app/core/history.py").read_bytes()).hexdigest(),
        "hash_mismatch_accepted": hash_mismatch_accepted,
        "forged_manifest_deleted_outside_project_sentinel": not sentinel.exists(),
        "forged_manifest_creation_refused": refused,
        "original_source_unchanged": source.read_bytes() == b"original source",
    }
    (output / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
