"""Synthetic actual FINAL -> reviewed delivery -> external-source compile/restore.

Core workflow only; no GUI, desktop focus, real student files or release action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication
from PySide6.QtPdf import QPdfDocument

from app.core.block_submission import BlockCheckInput
from app.core.build_evidence import final_build_evidence
from app.core.blocks.project_repository import load_project
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.core.pdf_state import PdfBuildRecord, PdfFreshness
from app.core.project_checkpoint import checkpoint_candidates, create_checkpoint, restore_checkpoint
from app.core.project_profile import ProjectProfile, load_profile, save_profile
from app.core.submission_check import BufferInput, CheckRequest
from app.core.submission_delivery import (
    DeliveryOptions, prepare_submission, publish_submission, submission_source_candidates,
)
from tests.v1_fixtures import create_project
from tools.probe_project_migration import digest_tree


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def final(root, tools, engine=LaTeXEngine.XELATEX):
    result = CompileManager(root, toolchain=tools, engine=engine).compile_now(
        BuildPurpose.FINAL, timeout_seconds=90)
    assert result and result.ok and result.input_evidence and result.input_evidence.stable, result
    return result


def pdf_text(path):
    pdf = QPdfDocument()
    assert pdf.load(str(path)) == QPdfDocument.Error.None_
    text = " ".join(pdf.getAllText(i).text() for i in range(pdf.pageCount()))
    pdf.close()
    return " ".join(text.split())


def run(output):
    app = QCoreApplication.instance() or QCoreApplication([])
    output = output.expanduser().resolve()
    output.mkdir(exist_ok=False)
    digest = digest_tree()
    tools = detect_toolchain()
    evidence = {"app_sha256": digest, "platform": platform.platform(), "python": sys.version,
                "kind": "Core synthetic workflow; NOT GUI or complete M5 acceptance", "cases": []}
    for kind in ("single", "multi", "block"):
        engine = LaTeXEngine.XELATEX if kind == "block" else LaTeXEngine.PDFLATEX
        sample = create_project(output, kind)
        project = sample.root.parent
        (project / "README.md").write_bytes(b"User original portable instructions.\r\n")
        (project / "manifest.json").write_bytes(b'{"user_original":true}\r\n')
        (project / "encoding-note.tex").write_bytes(b"% retained bytes \x81\xff\r\n")
        save_profile(project, ProjectProfile(engine=engine.value, word_max=5000), expected=load_profile(project))
        paths, _ = checkpoint_candidates(project)
        paths = tuple(sorted(set(paths) | {"README.md", "manifest.json"}))
        archive = output / (kind + ".icstex-checkpoint")
        saved = create_checkpoint(project, paths, archive)
        original = {p: (project / p).read_bytes() for p in paths}
        result = final(sample.root, tools, engine)
        proof = final_build_evidence(result)
        revision = proof.job_key.source_revision
        record = PdfBuildRecord(sample.root, PdfFreshness.CURRENT, result.pdf_file,
                                revision, revision, revision, result.build_id)
        block = None
        if kind == "block":
            block = BlockCheckInput(*((project / path).read_text(encoding="utf-8") for path in (
                ".icstex/blocks.json", ".icstex/layouts.json", ".icstex/sources.json", "styles/document-theme.json")))
        request = CheckRequest((kind, result.build_id), project, sample.root,
            (BufferInput(sample.root, sample.root.read_text(encoding="utf-8"), 0),),
            tools, engine, final=record, block=block, build_evidence=proof,
            source_revision=revision)
        bare = prepare_submission(request)
        default = publish_submission(bare, output / (kind + "-pdf-only"), accept_unconfirmed=True)
        assert [p.name for p in default.iterdir()] == ["submission.pdf"]
        source_paths, warnings = submission_source_candidates(project)
        assert {"README.md", "manifest.json", "encoding-note.tex"}.issubset(source_paths)
        options = DeliveryOptions(True, True, source_paths, "final.pdf")
        prepared = prepare_submission(request, options)
        package = publish_submission(prepared, output / (kind + "-delivery"), accept_unconfirmed=True)
        report_bytes = (package / "submission-report.json").read_bytes()
        assert str(output).encode() not in report_bytes
        report = json.loads(report_bytes)
        versions = report["build_tool_versions"]
        assert versions["source"] == "actual_final_stdout_startup_banners"
        assert versions["driver"]["program"] == "latexmk" and versions["driver"]["version"]
        assert versions["engine"]["program"] == ("XeTeX" if kind == "block" else "pdfTeX")
        assert versions["engine"]["version"] == result.tool_versions.engine.version
        assert report["word_target"] == [None, 5000]
        assert report["word_count"]["mode"] in {"texcount", "fallback"}
        for path in source_paths:
            assert (package / "source" / path).read_bytes() == (project / path).read_bytes()
        for entry in report["outputs"]:
            raw = (package / entry["path"]).read_bytes()
            assert sha(raw) == entry["sha256"] and len(raw) == entry["size"]
        expected = "Synthetic analysis." if kind == "block" else "Synthetic sample"
        assert expected in pdf_text(package / "final.pdf")
        assert (package / "final.pdf").read_bytes() == result.pdf_file.read_bytes()
        # Selected Block metadata also permits normal model reopening. Ordinary
        # TeX compilation still runs independently of that metadata.
        if kind == "block":
            loaded = load_project(package / "source")
            assert loaded["registry"].blocks()[0].content["text"] == "Synthetic analysis."
        outside = final(package / "source/main.tex", tools, engine)
        assert expected in pdf_text(outside.pdf_file)
        restored = restore_checkpoint(archive, output / (kind + "-restored"))
        assert restored.info == saved
        assert all((restored.project_dir / p).read_bytes() == raw for p, raw in original.items())
        if kind == "block":
            assert load_project(restored.project_dir)["registry"].blocks()
        restored_final = final(restored.project_dir / "main.tex", tools, engine)
        assert expected in pdf_text(restored_final.pdf_file)
        assert all((project / p).read_bytes() == raw for p, raw in original.items())
        evidence["cases"].append({"kind": kind, "source_files": len(source_paths),
            "build_id": result.build_id, "build_tool_versions": versions,
            "frozen_inputs": len(prepared.inputs), "word_mode": report["word_count"]["mode"],
            "effective_words": report["word_count"]["effective_words"], "unconfirmed": len(prepared.unconfirmed),
            "originals_unchanged": True, "pdf_only_default": True,
            "selected_source_bytes_preserved": True, "source_readme_manifest_preserved": True,
            "block_metadata_reopened": kind == "block",
            "delivered_pdf_sha256": sha((package / "final.pdf").read_bytes()),
            "source_recompiled_pdf_sha256": sha(outside.pdf_file.read_bytes()),
            "restored_pdf_sha256": sha(restored_final.pdf_file.read_bytes()),
            "report_sha256": sha(report_bytes), "selection_warnings": warnings})
    assert digest_tree() == digest
    evidence["limits"] = ["Core only; this run does not exercise GUI entry points",
        "Initial stdout self-reports driver/engine versions; not binary identity or auxiliary tool/package/font versions",
        "Selected project inputs only; system font/package and unknown macro coverage is not guaranteed",
        "No native GUI, Windows, IME/AX, power-loss, human usability, upload or release acceptance"]
    (output / "result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
