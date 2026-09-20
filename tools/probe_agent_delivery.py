"""Synthetic actual AgentWorkspace and stdio MCP export acceptance.

No GUI, real student files, real credentials, application packaging or release.
The legacy source package is not the GUI's per-file reviewed submission workflow.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QCoreApplication
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from app.core.agent_workspace import AgentGrants, AgentWorkspace, AgentWorkspaceError
from app.core import project_checkpoint
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from tests.v1_fixtures import create_project
from tools.probe_submission_delivery import pdf_text
from tools.probe_agent_delivery_gaps import source_digest, sha


def workspace_for(sample, exports):
    return AgentWorkspace(sample.root.parent, grants=AgentGrants(allow_compile=True, export_root=exports))


def verify_package(project, target, value):
    manifest = json.loads((target / ".icstex-package/manifest.json").read_bytes())
    assert manifest == value["manifest"]
    assert set(value) == {"kind", "target", "files", "manifest"}
    for entry in manifest["files"]:
        raw = (target / entry["path"]).read_bytes()
        assert raw == (project / entry["path"]).read_bytes()
        assert sha(raw) == entry["sha256"]
    assert not {"signing.pem", "id_ed25519", ".venv/cache.txt", "tokens.json"} & set(value["files"])
    assert "README.md" in value["files"] and "manifest.json" in value["files"]


async def stdio_check(sample, exports, kind):
    observed = {}
    pdf_name, source_name = "stdio-" + kind + ".pdf", "stdio-" + kind + "-source"
    for compile_grant in (False, True):
        args = ["-m", "app.mcp_server", "--project-root", str(sample.root.parent),
                "--export-root", str(exports)]
        if compile_grant:
            args.append("--allow-compile")
        parameters = StdioServerParameters(command=sys.executable, args=args, cwd=str(REPO))
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                export_tool = next(item for item in tools.tools if item.name == "export_artifact")
                assert len(tools.tools) == 11
                assert set(export_tool.input_schema["properties"]) == {
                    "kind", "target_path", "root_path", "assemble_blocks", "expected_project_sha256"}
                inspected = await session.call_tool("inspect_project", {})
                assert not inspected.is_error, inspected
                response = await session.call_tool("export_artifact", {
                    "kind": "pdf", "target_path": pdf_name})
                if not compile_grant:
                    assert response.is_error and not (exports / pdf_name).exists()
                    observed["compile_denial_before_output"] = True
                    continue
                assert not response.is_error, response
                value = response.structured_content
                assert set(value) == {"kind", "target", "sha256", "size"}
                original = (exports / pdf_name).read_bytes()
                assert sha(original) == value["sha256"]
                expected = "Synthetic analysis." if kind == "block" else "Synthetic sample"
                assert expected in pdf_text(exports / pdf_name)
                repeated = await session.call_tool("export_artifact", {
                    "kind": "pdf", "target_path": pdf_name})
                assert repeated.is_error and (exports / pdf_name).read_bytes() == original
                package = await session.call_tool("export_artifact", {
                    "kind": "package", "target_path": source_name})
                assert not package.is_error, package
                verify_package(sample.root.parent, exports / source_name, package.structured_content)
                observed.update(pdf_sha256=sha(original), exact_schema_and_11_tools=True,
                                actual_package_verified=True, existing_target_refused=True)
    return observed


def run(output):
    application = QCoreApplication.instance() or QCoreApplication([])
    output = output.expanduser().resolve()
    output.mkdir(exist_ok=False)
    exports = output / "exports"
    exports.mkdir()
    before = source_digest()
    evidence = {"app_sha256": before, "platform": platform.platform(), "python": sys.version,
                "cases": [], "faults": []}
    samples = {}
    for kind in ("single", "multi", "block"):
        sample = samples[kind] = create_project(output, kind)
        project = sample.root.parent
        for name, raw in {"README.md": b"original user README\r\n",
                          "manifest.json": b'{"user_original":true}\r\n',
                          "encoding-note.txt": b"original bytes \x81\xff\r\n",
                          "signing.pem": b"SYNTHETIC NOT A REAL KEY", "id_ed25519": b"SYNTHETIC PLACEHOLDER",
                          "tokens.json": b'{"synthetic_non_secret":true}'}.items():
            (project / name).write_bytes(raw)
        (project / ".venv").mkdir()
        (project / ".venv/cache.txt").write_bytes(b"synthetic cache")
        originals = {path.relative_to(project).as_posix(): path.read_bytes()
                     for path in project.rglob("*") if path.is_file()}
        workspace = workspace_for(sample, exports)
        original_result = workspace._compile_project_result
        def record_result(**kwargs):
            result = original_result(**kwargs)
            (output / (kind + "-actual-compile.json")).write_text(json.dumps({
                "outcome": result.outcome.value, "returncode": result.returncode,
                "errors": [repr(error) for error in result.errors],
                "input_evidence_stable": bool(result.input_evidence and result.input_evidence.stable),
                "stdout": result.stdout, "stderr": result.stderr,
            }, indent=2), encoding="utf-8")
            return result
        with patch.object(workspace, "_compile_project_result", side_effect=record_result):
            delivered = workspace.export_artifact("pdf", kind + ".pdf")
        assert set(delivered) == {"kind", "target", "sha256", "size"}
        assert delivered["sha256"] == sha((exports / (kind + ".pdf")).read_bytes())
        expected = "Synthetic analysis." if kind == "block" else "Synthetic sample"
        assert expected in pdf_text(exports / (kind + ".pdf"))
        portable = workspace.export_artifact("package", kind + "-source")
        target = exports / (kind + "-source")
        verify_package(project, target, portable)
        external = CompileManager(target / "main.tex", toolchain=detect_toolchain(),
            engine=LaTeXEngine.XELATEX, restricted_io=True, project_scope=target).compile_now(
                BuildPurpose.FINAL, timeout_seconds=90)
        assert external and external.ok, external
        assert expected in pdf_text(external.pdf_file)
        assert all((project / name).read_bytes() == raw for name, raw in originals.items())
        evidence["cases"].append({"kind": kind, "pdf_sha256": delivered["sha256"],
            "source_file_count": len(portable["files"]), "source_bytes_unchanged": True,
            "source_recompiled_pdf_sha256": sha(external.pdf_file.read_bytes())})

    sample = samples["multi"]
    workspace = workspace_for(sample, exports)
    original_compile = workspace._compile_project_result
    old_child = sample.draft_path.read_bytes()
    def finish_then_change(**kwargs):
        result = original_compile(**kwargs)
        assert result.ok and result.input_evidence.stable
        info = sample.draft_path.stat()
        new_child = old_child.replace(b"See Section", b"See section")
        assert new_child != old_child and len(new_child) == len(old_child)
        sample.draft_path.write_bytes(new_child)
        os.utime(sample.draft_path, ns=(info.st_atime_ns, info.st_mtime_ns))
        return result
    with patch.object(workspace, "_compile_project_result", side_effect=finish_then_change):
        try:
            workspace.export_artifact("pdf", "stale-refused.pdf")
        except (AgentWorkspaceError, OSError, ValueError):
            pass
        else:
            raise AssertionError("Changed input was exported")
    assert not (exports / "stale-refused.pdf").exists()
    assert sample.draft_path.read_bytes() != old_child
    evidence["faults"].append("Actual FINAL followed by same-size/same-mtime input change refused")
    sample.draft_path.write_bytes(old_child)

    original_publish = project_checkpoint._OutputParent.publish_file
    def occupy(parent, name, signature):
        parent.target.write_bytes(b"synthetic late target owner")
        return original_publish(parent, name, signature)
    with patch.object(project_checkpoint._OutputParent, "publish_file", occupy):
        try:
            workspace.export_artifact("pdf", "late-owner.pdf")
        except FileExistsError:
            pass
        else:
            raise AssertionError("Late target was overwritten")
    assert (exports / "late-owner.pdf").read_bytes() == b"synthetic late target owner"
    evidence["faults"].append("Actual PDF export preserves late-created target bytes")

    original_write = project_checkpoint._write_restored
    def change_after_write(directory, relative, *args, **kwargs):
        value = original_write(directory, relative, *args, **kwargs)
        if relative == sample.draft_path.relative_to(sample.root.parent).as_posix():
            sample.draft_path.write_bytes(old_child + b"\nExternal changed source.\n")
        return value
    with patch.object(project_checkpoint, "_write_restored", change_after_write):
        try:
            workspace.export_artifact("package", "mixed-refused")
        except (OSError, ValueError):
            pass
        else:
            raise AssertionError("Mixed source was published")
    assert not (exports / "mixed-refused").exists()
    evidence["faults"].append("Actual package staging change refuses publication and preserves external edit")
    sample.draft_path.write_bytes(old_child)
    evidence["stdio"] = {kind: asyncio.run(stdio_check(samples[kind], exports, kind))
                         for kind in ("single", "block")}
    assert source_digest() == before
    evidence["limits"] = ["No GUI/per-file review or academic certification in legacy MCP source export",
        "No OS-atomic exclusion of noncooperating source writers; content rechecks are bounded observations",
        "No native Windows, physical input, installation or release acceptance",
        "Source contents may contain private information despite conservative name filtering"]
    (output / "result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
