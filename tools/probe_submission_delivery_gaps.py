"""Bounded pre-M5 defect reproduction; success means gaps observed, NOT fixed.

Synthetic files only. No UI focus, real secrets, upload or Git mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QFileDialog
from app.core.blocks.export_package import export_package
from app.core.pdf_state import PdfFreshness
from app.gui.theme import apply_theme
from tests.v1_fixtures import create_project
from tools.probe_history_restore import app_digest
from tools.probe_project_checkpoint_gui import close, window_for
from tools.probe_recovered_drafts import compile_and_check


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(output):
    if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
        raise SystemExit("Requires QT_QPA_PLATFORM=offscreen; native UI is not authorized.")
    app = QApplication.instance() or QApplication([])
    assert app.platformName() == "offscreen"
    app.setQuitOnLastWindowClosed(False)
    apply_theme(app)
    output = output.expanduser().resolve()
    output.mkdir(exist_ok=False)
    digest = app_digest()
    evidence = {"app_sha256": digest, "status": "Pre-M5 gaps reproduced; NOT acceptance or a fix", "gaps": []}
    fixture = create_project(output, "multi")
    window = window_for(output, "source-owner")
    try:
        window.project_files.set_project_root(fixture.root.parent)
        window.open_file(fixture.root)
        window.show()
        build_hash = compile_and_check(window, "multi", "Synthetic sample", scan_page=True)
        root = fixture.root.resolve()
        record = window.pdf_state.record_for(root)
        assert record.freshness is PdfFreshness.CURRENT
        # A real external dependency write after FINAL, before queued watcher
        # delivery. No GUI event drain between this write and actual export.
        old = fixture.draft_path.read_bytes()
        info = fixture.draft_path.stat()
        fixture.draft_path.write_bytes(old + b"\nChanged after FINAL, before watcher delivery.\n")
        os.utime(fixture.draft_path, ns=(info.st_atime_ns, info.st_mtime_ns))
        target = output / "stale-export.pdf"
        with patch.object(QFileDialog, "getSaveFileName", return_value=(str(target), "PDF")):
            accepted = window.export_pdf()
        assert accepted and target.is_file() and sha(target.read_bytes()) == build_hash
        assert fixture.draft_path.read_bytes() != old
        evidence["gaps"].append({"id": "stale-before-watcher", "actual_window_export_accepted": accepted,
            "changed_input": "chapters/analysis.tex", "old_final_exported_sha256": build_hash,
            "mtime_preserved": fixture.draft_path.stat().st_mtime_ns == info.st_mtime_ns})
    finally:
        close(window)

    project = output / "portable-original"
    project.mkdir()
    for name, raw in {"main.tex": b"synthetic source", "README.md": b"User-authored synthetic instructions",
                      "signing.pem": b"SYNTHETIC NON-SECRET PLACEHOLDER", "id_ed25519": b"NOT A REAL KEY"}.items():
        (project / name).write_bytes(raw)
    (project / ".venv").mkdir()
    (project / ".venv/cache.txt").write_bytes(b"synthetic environment cache")
    exported = export_package(project, output / "portable-copy")
    leaked_names = sorted(set(exported.files) & {"signing.pem", "id_ed25519", ".venv/cache.txt"})
    assert leaked_names == [".venv/cache.txt", "id_ed25519", "signing.pem"]
    mismatches = [e["path"] for e in exported.manifest["files"]
                  if sha((exported.target_dir / e["path"]).read_bytes()) != e["sha256"]]
    assert mismatches == ["README.md"]
    evidence["gaps"].append({"id": "implicit-file-selection", "synthetic_sensitive_names_copied": leaked_names})
    evidence["gaps"].append({"id": "generated-readme-overwrites-user-file", "manifest_mismatches": mismatches})

    source = output / "fault-original"
    source.mkdir()
    for name in ("a.tex", "b.tex"):
        (source / name).write_bytes(("new " + name).encode())
    target = output / "previous-success"
    target.mkdir()
    (target / "a.tex").write_bytes(b"previous successful a")
    (target / "manifest.json").write_bytes(b"previous manifest retained")
    real_copy = shutil.copy2
    calls = []
    def fail_after_first(src, dst, *args, **kwargs):
        calls.append(Path(src).name)
        if len(calls) == 2:
            raise OSError("Synthetic disk full after first copy")
        return real_copy(src, dst, *args, **kwargs)
    with patch("app.core.blocks.export_package.shutil.copy2", side_effect=fail_after_first):
        try:
            export_package(source, target)
        except OSError:
            pass
        else:
            raise AssertionError("Expected injected copy failure")
    assert (target / "a.tex").read_bytes() == b"new a.tex"
    assert (target / "manifest.json").read_bytes() == b"previous manifest retained"
    evidence["gaps"].append({"id": "failed-export-mutates-previous-delivery", "first_file_overwritten": True,
                             "old_manifest_left_with_new_file": True})

    mixed = output / "mixed-copy"
    calls.clear()
    before_a = (source / "a.tex").read_bytes()
    def change_between_copies(src, dst, *args, **kwargs):
        value = real_copy(src, dst, *args, **kwargs)
        calls.append(Path(src).name)
        if len(calls) == 1:
            for name in ("a.tex", "b.tex"):
                (source / name).write_bytes(("later " + name).encode())
        return value
    with patch("app.core.blocks.export_package.shutil.copy2", side_effect=change_between_copies):
        export_package(source, mixed)
    assert (mixed / "a.tex").read_bytes() == before_a
    assert (mixed / "b.tex").read_bytes() == b"later b.tex"
    assert (source / "a.tex").read_bytes() != before_a
    evidence["gaps"].append({"id": "mixed-version-package", "a_from_before_and_b_from_after": True})
    assert app_digest() == digest
    evidence["limits"] = ["Synthetic-only source-level export checks; not a repair or a complete M5 audit",
        "Dialog destination supplied without native picker or desktop input",
        "Old controller state exists before watcher delivery; no general watcher-failure claim",
        "No real key material, upload, package application build, install or release"]
    (output / "result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
