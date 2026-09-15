"""Actual AgentWorkspace export defects using disposable synthetic files only.

Exit zero means the named old-path defects were reproduced, not repaired.
No GUI, real credentials, network, Git mutation or application packaging.
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

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.core.agent_workspace import AgentGrants, AgentWorkspace


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def source_digest():
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def run(output):
    output = output.expanduser().resolve()
    output.mkdir(exist_ok=False)
    project, exports = output / "synthetic-project", output / "synthetic-deliveries"
    project.mkdir()
    exports.mkdir()
    (project / "main.tex").write_bytes(
        b"% !TeX program = pdflatex\n\\documentclass{article}\n"
        b"\\begin{document}\n\\input{child}\n\\end{document}\n")
    child = project / "child.tex"
    child.write_bytes(b"Old synthetic content.\n")
    workspace = AgentWorkspace(project, grants=AgentGrants(
        allow_compile=True, export_root=exports))
    before = source_digest()
    evidence = {"app_sha256": before, "status": "Defects reproduced, NOT acceptance", "gaps": []}

    original_compile = workspace._compile_project_run
    observed = {}

    def compile_then_change(**kwargs):
        result = original_compile(**kwargs)
        assert result["ok"] and result["purpose"] == "final", result
        info = child.stat()
        observed["pdf_sha256"] = sha((project / result["pdfFile"]).read_bytes())
        observed["compiled_child_sha256"] = sha(child.read_bytes())
        child.write_bytes(b"New synthetic content.\n")
        os.utime(child, ns=(info.st_atime_ns, info.st_mtime_ns))
        observed["mtime_preserved"] = child.stat().st_mtime_ns == info.st_mtime_ns
        return result

    with patch.object(workspace, "_compile_project_run", side_effect=compile_then_change):
        stale = workspace.export_artifact("pdf", "stale.pdf")
    assert stale["sha256"] == observed["pdf_sha256"]
    assert sha(child.read_bytes()) != observed["compiled_child_sha256"]
    evidence["gaps"].append({"id": "actual-agent-pdf-input-changed-after-final",
        "actual_export_accepted": True, **observed})

    original_copy = workspace._atomic_copy
    occupied_bytes = b"SYNTHETIC PREEXISTING DELIVERY CREATED AT COPY BOUNDARY"

    def occupy_before_copy(source, target):
        assert not target.exists()
        target.write_bytes(occupied_bytes)
        original_copy(source, target)

    with patch.object(workspace, "_atomic_copy", side_effect=occupy_before_copy):
        replaced = workspace.export_artifact("pdf", "occupied.pdf")
    assert (exports / "occupied.pdf").read_bytes() != occupied_bytes
    evidence["gaps"].append({"id": "actual-agent-pdf-replaces-late-existing-target",
        "previous_bytes_overwritten": True, "delivered_sha256": replaced["sha256"]})

    for name, payload in {
        "README.md": b"User-authored synthetic README bytes\r\n",
        "signing.pem": b"SYNTHETIC NON-SECRET PLACEHOLDER",
        "id_ed25519": b"NOT A REAL KEY",
    }.items():
        (project / name).write_bytes(payload)
    (project / ".venv").mkdir()
    (project / ".venv/cache.txt").write_bytes(b"synthetic environment cache")
    package = workspace.export_artifact("package", "portable")
    private = sorted(set(package["files"]) & {"signing.pem", "id_ed25519", ".venv/cache.txt"})
    assert private == [".venv/cache.txt", "id_ed25519", "signing.pem"]
    mismatches = [entry["path"] for entry in package["manifest"]["files"]
        if sha((exports / "portable" / entry["path"]).read_bytes()) != entry["sha256"]]
    assert mismatches == ["README.md"]
    evidence["gaps"].append({"id": "actual-agent-package-private-names",
        "copied_synthetic_names": private, "existing_empty_stage_call_succeeded": True})
    evidence["gaps"].append({"id": "actual-agent-package-readme-manifest-mismatch",
        "manifest_mismatches": mismatches})

    (project / "a.tex").write_bytes(b"old a")
    (project / "b.tex").write_bytes(b"old b")
    original_copy2 = shutil.copy2
    changed = False

    def change_after_a(source, destination, *args, **kwargs):
        nonlocal changed
        result = original_copy2(source, destination, *args, **kwargs)
        if Path(source) == project / "a.tex":
            assert not changed
            changed = True
            (project / "a.tex").write_bytes(b"new a")
            (project / "b.tex").write_bytes(b"new b")
        return result

    with patch("app.core.blocks.export_package.shutil.copy2", side_effect=change_after_a):
        workspace.export_artifact("package", "mixed")
    assert changed and (exports / "mixed/a.tex").read_bytes() == b"old a"
    assert (exports / "mixed/b.tex").read_bytes() == b"new b"
    evidence["gaps"].append({"id": "actual-agent-package-mixed-source-version",
        "published_old_a_with_new_b": True})
    assert source_digest() == before
    evidence["limits"] = [
        "Actual AgentWorkspace methods, not an MCP transport/session authorization test",
        "Controlled copy-boundary faults; not OS-atomic external-writer exclusion",
        "Synthetic placeholders only; no real private key material",
        "No GUI/native interaction or performance acceptance",
    ]
    (output / "result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
