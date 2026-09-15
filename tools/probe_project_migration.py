"""Background synthetic copy/legacy conversion/reopen/FINAL; no GUI acceptance."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QCoreApplication
from PySide6.QtPdf import QPdfDocument
from app.core.blocks.migration import legacy_fixture
from app.core.blocks.project_repository import load_project
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.core.project_checkpoint import DraftInput
from app.core.project_migration import inspect_project_migration, migrate_project_copy
from app.core.project_recovery import read_recovery_copy
from tests.v1_fixtures import _png, create_project


def digest_tree():
    digest = hashlib.sha256()
    for path in sorted((REPO / "app").rglob("*.py")):
        digest.update(path.relative_to(REPO).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def run(output):
    app = QCoreApplication.instance() or QCoreApplication([])
    output = output.expanduser().absolute()
    output.mkdir(exist_ok=False)
    source = digest_tree()
    toolchain = detect_toolchain()
    report = {"app_sha256": source, "platform": platform.platform(), "python": sys.version,
              "boundary": "Synthetic core copy/reopen and explicit FINAL only; no GUI, switch, install or release",
              "cases": []}
    for kind in ("multi", "block", "legacy"):
        if kind == "legacy":
            project = output / "旧格式 项目"
            (project / ".icstex").mkdir(parents=True)
            (project / "figures").mkdir()
            data = legacy_fixture()
            data["legacySideBySideFigures"][0].update(leftCaption="Left synthetic image", rightCaption="Right synthetic image")
            data["customMetadata"] = {"zero": 0, "flag": False}
            data["legacyLatexSnippets"][0]["latex"] = "% preserved verbatim\r\n\\unknown{not compiled}\t"
            raw = json.dumps(data, ensure_ascii=False, indent=1).replace("\n", "\r\n").encode()
            (project / ".icstex/blocks.json").write_bytes(raw)
            for name in ("a.png", "b.png"):
                (project / "figures" / name).write_bytes(_png())
            (project / "main.tex").write_bytes(b"% original manual source\r\n\\unknown{keep}\r\n")
        else:
            project = create_project(output, kind).root.parent
        (project / "encoding-note.tex").write_bytes(b"% " + "原始字节".encode("gbk") + b"\r\n")
        original = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*") if p.is_file()}
        review = inspect_project_migration(project)
        draft = DraftInput("source-1", "source-text", "main.tex", "独立草稿，不自动套用。\n".encode())
        result = migrate_project_copy(review, output / (kind + "-copy"), drafts=[draft])
        copy = read_recovery_copy(result.directory)
        assert dict(copy.files) == dict(review.candidate)
        assert dict(copy.drafts)[draft.id] == draft.payload
        assert all((project / p).read_bytes() == b for p, b in original.items())
        if kind == "legacy":
            assert all((result.directory / "recovery-evidence/original" / p).read_bytes() == b for p, b in original.items())
            assert "customMetadata" in review.unmapped_keys
            loaded = load_project(result.project_dir)
            snippet = next(b for b in loaded["registry"].blocks() if b.type == "rawLatex")
            assert snippet.content["latex"] == data["legacyLatexSnippets"][0]["latex"]
            assert snippet.content["trusted"] is False
            snippet_source = (result.project_dir / "blocks" / (snippet.id + ".tex")).read_bytes()
            assert snippet_source == (f"% ICSTEX:BEGIN block={snippet.id}\n"
                "% ICSTEX:raw-latex blocked (requires explicit session trust)\n"
                f"% ICSTEX:END block={snippet.id}\n").encode()
        if kind != "multi":
            assert load_project(result.project_dir)["layout"] is not None
        # Separate, explicit synthetic build; copying alone cannot start it.
        final = CompileManager(result.project_dir / "main.tex", toolchain=toolchain,
                               engine=LaTeXEngine.XELATEX).compile_now(BuildPurpose.FINAL, timeout_seconds=90)
        assert final and final.ok and final.pdf_file, final.combined_output if final else "No build"
        pdf = QPdfDocument()
        assert pdf.load(str(final.pdf_file)) == QPdfDocument.Error.None_
        text = "\n".join(pdf.getAllText(page).text() for page in range(pdf.pageCount()))
        expected = {"multi": "Synthetic sample", "block": "Synthetic analysis.", "legacy": "Left synthetic image"}[kind]
        assert expected in text, text
        if kind == "legacy":
            assert "Right synthetic image" in text
            assert "not compiled" not in text
        pages = pdf.pageCount()
        pdf.close()
        assert all((project / p).read_bytes() == b for p, b in original.items())
        assert all((result.project_dir / p).read_bytes() == b for p, b in review.candidate)
        again = inspect_project_migration(result.project_dir, paths=[p for p, _ in review.candidate])
        assert again.kind != "legacy-conversion"
        assert dict(again.original) == dict(again.candidate)
        report["cases"].append({"kind": kind, "files": len(result.info.files), "pages": pages,
            "final_pdf_sha256": hashlib.sha256(final.pdf_file.read_bytes()).hexdigest(),
            "original_bytes_preserved": True, "separate_draft_preserved": True,
            "real_loader_reopened": kind != "multi", "second_copy_byte_exact": True,
            "unmapped_keys": review.unmapped_keys, "replaced_in_copy": review.replaced})
    assert digest_tree() == source, "Source changed during verification"
    (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
