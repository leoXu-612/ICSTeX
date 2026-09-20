"""Check whether a warm FINAL can relabel an externally substituted valid PDF.

Synthetic-only observation, not a repair or full acceptance test. No GUI, upload,
real writing project, credential access or release mutation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication
from app.core.agent_workspace import AgentGrants, AgentWorkspace
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine
from tools.probe_agent_delivery_gaps import sha, source_digest
from tools.probe_submission_delivery import pdf_text


def run(output, engine=LaTeXEngine.PDFLATEX, expect_fixed=False):
    application = QCoreApplication.instance() or QCoreApplication([])
    output = output.expanduser().resolve()
    output.mkdir(exist_ok=False)
    app_hash = source_digest()
    projects = []
    results = []
    for name, text in (("expected", "EXPECTED SYNTHETIC PAPER"), ("unrelated", "UNRELATED SYNTHETIC PAPER")):
        project = output / name
        project.mkdir()
        root = project / "main.tex"
        root.write_text(f"% !TeX program = {engine.value}\n\\documentclass{{article}}\n\\begin{{document}}\n" + text + "\n\\end{document}\n", encoding="utf-8")
        manager = CompileManager(root, engine=engine, restricted_io=True)
        result = manager.compile_now(BuildPurpose.FINAL, timeout_seconds=90)
        assert result and result.ok and result.input_evidence.stable
        projects.append(project)
        results.append(result)
    expected, unrelated = results
    source_before = (projects[0] / "main.tex").read_bytes()
    original_pdf = expected.pdf_file.read_bytes()
    replacement = unrelated.pdf_file.read_bytes()
    info = expected.pdf_file.stat()
    expected.pdf_file.write_bytes(replacement)
    os.utime(expected.pdf_file, ns=(info.st_atime_ns, info.st_mtime_ns))
    exports = output / "exports"
    exports.mkdir()
    workspace = AgentWorkspace(projects[0], grants=AgentGrants(allow_compile=True, export_root=exports))
    observed = {"app_sha256": app_hash, "engine": engine.value,
                "original_pdf_sha256": sha(original_pdf),
                "substituted_pdf_sha256": sha(replacement),
                "mtime_preserved": expected.pdf_file.stat().st_mtime_ns == info.st_mtime_ns}
    try:
        exported = workspace.export_artifact("pdf", "after-final.pdf")
    except (OSError, ValueError, RuntimeError) as exc:
        observed.update(export_refused=True, error_type=type(exc).__name__, error=str(exc))
    else:
        text = pdf_text(exports / "after-final.pdf")
        observed.update(export_refused=False, exported_sha256=exported["sha256"], exported_text=text,
                        substituted_pdf_accepted=("UNRELATED SYNTHETIC PAPER" in text))
    assert (projects[0] / "main.tex").read_bytes() == source_before
    if expect_fixed:
        assert not observed["export_refused"], observed
        assert not observed["substituted_pdf_accepted"], observed
        assert "EXPECTED SYNTHETIC PAPER" in observed["exported_text"], observed
        # This second case exercises the driver's input cache, not only PDF output.
        root = projects[0] / "main.tex"
        source_info = root.stat()
        revised = source_before.replace(b"EXPECTED", b"REVISION")
        assert len(revised) == len(source_before) and revised != source_before
        root.write_bytes(revised)
        os.utime(root, ns=(source_info.st_atime_ns, source_info.st_mtime_ns))
        workspace.export_artifact("pdf", "revised-final.pdf")
        revised_text = pdf_text(exports / "revised-final.pdf")
        assert "REVISION SYNTHETIC PAPER" in revised_text, revised_text
        assert "EXPECTED SYNTHETIC PAPER" not in revised_text, revised_text
        assert root.read_bytes() == revised
        observed.update(revised_text=revised_text, same_size_same_mtime_source_rebuilt=True)
    assert source_digest() == app_hash
    observed["limits"] = "Two valid synthetic PDFs; this is a single cache/provenance observation, not all build modes"
    (output / "result.json").write_text(json.dumps(observed, indent=2), encoding="utf-8")
    print(json.dumps(observed, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", choices=[value.value for value in LaTeXEngine if value is not LaTeXEngine.AUTO], default="pdflatex")
    parser.add_argument("--expect-fixed", action="store_true")
    args = parser.parse_args()
    run(args.output, LaTeXEngine(args.engine), args.expect_fixed)
