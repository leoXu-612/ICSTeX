"""Synthetic filesystem checkpoint/restore/reopen/FINAL probe, not GUI QA."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

from app.core.blocks.project_repository import load_project
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.core.project_checkpoint import DraftInput, create_checkpoint, inspect_checkpoint, restore_checkpoint
from v1_fixtures import create_project


def app_digest():
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def run(output):
    output = output.expanduser().absolute()
    output.mkdir(parents=False, exist_ok=False)
    initial_app = app_digest()
    report = {"app_sha256": initial_app, "python": sys.version, "platform": platform.platform(),
              "boundary": "synthetic core/filesystem/reopen/FINAL only; no GUI, install, release or student files",
              "workflows": []}
    tools = detect_toolchain()
    for kind in ("multi", "block"):
        fixture = create_project(output, kind)
        project = fixture.root.parent
        legacy = project / "legacy-gbk-crlf.tex"
        legacy.write_bytes(b"% " + "中文原始字节".encode("gbk") + b"\r\n")
        empty = project / "empty.bib"
        empty.write_bytes(b"")
        original = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        drafts = [DraftInput("source-1", "source-text", fixture.draft_path.relative_to(project).as_posix(),
                             fixture.draft_text.encode("utf-8")),
                  DraftInput("untitled-1", "source-text", None, "未命名、未保存的草稿\n".encode())]
        if kind == "block":
            state = load_project(project)
            block_draft = {"format": "synthetic-block-draft-probe", "version": 1,
                           "blocks": [block.to_dict() for block in state["registry"].blocks()],
                           "unapplied": {"alias": "synthetic pending alias"}}
            drafts.append(DraftInput("block-1", "block-state", ".icstex/blocks.json",
                                     json.dumps(block_draft, ensure_ascii=False).encode()))
        archive = output / f"{kind}.icstex-checkpoint"
        start = time.monotonic()
        info = create_checkpoint(project, tuple(original), archive, drafts=drafts)
        capture_seconds = time.monotonic() - start
        assert info == inspect_checkpoint(archive)
        assert str(project).encode() not in info.manifest()
        start = time.monotonic()
        result = restore_checkpoint(archive, output / f"{kind}-restored")
        restore_seconds = time.monotonic() - start
        assert all((project / path).read_bytes() == data for path, data in original.items())
        restored = {p.relative_to(result.project_dir).as_posix(): p.read_bytes()
                    for p in result.project_dir.rglob("*") if p.is_file()}
        assert restored == original
        for draft in drafts:
            suffix = ".txt" if draft.kind == "source-text" else ".json"
            assert (result.drafts_dir / (draft.id + suffix)).read_bytes() == draft.payload
        if kind == "block":
            reopened = load_project(result.project_dir)
            assert [b.to_dict() for b in reopened["registry"].blocks()] == [
                b.to_dict() for b in state["registry"].blocks()]
            assert reopened["layout"].to_dict() == state["layout"].to_dict()
        # Explicit synthetic compilation, separate from checkpoint/restore authority.
        compiled = CompileManager(result.project_dir / "main.tex", toolchain=tools,
                                  engine=LaTeXEngine.XELATEX).compile_now(BuildPurpose.FINAL, timeout_seconds=90)
        assert compiled is not None and compiled.ok and compiled.pdf_file, (
            compiled.combined_output if compiled else "No FINAL result")
        assert all((project / path).read_bytes() == data for path, data in original.items())
        assert all((result.project_dir / path).read_bytes() == data for path, data in original.items())
        try:
            restore_checkpoint(archive, result.directory)
        except FileExistsError:
            pass
        else:
            raise AssertionError("Existing restore destination was accepted")
        report["workflows"].append({
            "kind": kind, "files": len(info.files), "drafts": len(info.drafts),
            "selected_bytes": sum(entry.size for entry in info.files),
            "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "final_pdf_sha256": hashlib.sha256(compiled.pdf_file.read_bytes()).hexdigest(),
            "capture_seconds": capture_seconds, "restore_seconds": restore_seconds,
            "manifest": json.loads(info.manifest()), "original_unchanged": True,
            "restored_bytes_match": True, "separate_drafts_match": True,
            "existing_destination_refused": True,
        })
    assert app_digest() == initial_app, "App source changed during probe"
    (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
