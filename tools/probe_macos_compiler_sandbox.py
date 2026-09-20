"""Incremental real-chain checks for the macOS restricted compiler backend.

Explicit invocation only; owns synthetic fixtures, never opens a GUI or packages.
Each case has a distinct directory and refuses to overwrite previous evidence.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.core.compiler import BuildPurpose, CompileManager, CompileOutcome
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.core.macos_compiler_sandbox import macos_sandbox_launch
from app.core.project_profile import PROFILE_PATH, ProjectProfile, profile_bytes


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity():
    result = hashlib.sha256()
    for path in sorted(p for folder in ("app", "tests") for p in (REPO / folder).rglob("*.py")):
        result.update(path.relative_to(REPO).as_posix().encode() + b"\0")
        result.update(path.read_bytes() + b"\0")
    return result.hexdigest()


def write_report(directory, value):
    (directory / "report.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in value.items() if k not in ("stdout", "stderr", "command")},
                     ensure_ascii=False), flush=True)


def compile_case(directory, engine, *, bibliography=False):
    project = directory / "Chinese path with spaces"
    project.mkdir()
    root = project / "main.tex"
    preamble = (r"\documentclass{article}" if engine is LaTeXEngine.PDFLATEX else
                r"\documentclass[fontset=fandol]{ctexart}")
    content = "Mac restricted compile. $E=mc^2$."
    if engine is not LaTeXEngine.PDFLATEX:
        content += " " + "\u4e2d\u6587\u5f15\u7528\u7f16\u8bd1\u9a8c\u8bc1\u3002"
    if bibliography:
        (project / "refs.bib").write_text('@book{sample,author={Example, Alex},title={Synthetic Reference},year={2026}}\n')
        if bibliography == "biber":
            preamble += "\n" + r"\usepackage[backend=biber,style=numeric]{biblatex}\addbibresource{refs.bib}"
            content += r"\cite{sample}\printbibliography"
        else:
            content += r"\cite{sample}\bibliographystyle{plain}\bibliography{refs}"
    root.write_text(preamble + "\n\\begin{document}\n" + content + "\n\\end{document}\n")
    original = {p.name: sha(p) for p in project.iterdir() if p.is_file()}
    manager = CompileManager(root, toolchain=detect_toolchain(), engine=engine,
                             restricted_io=True, project_scope=project)
    result = manager.compile_now(BuildPurpose.FINAL, timeout_seconds=90)
    value = {"case": engine.value, "outcome": result.outcome.value,
             "returncode": result.returncode, "seconds": result.duration_seconds,
             "command": result.command, "stdout": result.stdout, "stderr": result.stderr,
             "source_unchanged": all(sha(project / name) == digest for name, digest in original.items()),
             "input_evidence_stable": bool(result.input_evidence and result.input_evidence.stable),
             "errors": [str(e) for e in result.errors]}
    if result.ok:
        value["pdf_sha256"] = sha(result.pdf_file)
        value["pdf_path"] = str(result.pdf_file)
        value["extracted_text"] = subprocess.check_output(["pdftotext", str(result.pdf_file), "-"], text=True)
    write_report(directory, value)
    assert result.ok and value["source_unchanged"] and value["input_evidence_stable"], value
    if bibliography:
        assert "Synthetic Reference" in value["extracted_text"]
        assert ("biber" if bibliography == "biber" else "bibtex") in result.stdout.lower()
        assert not any("undefined" in str(w).lower() for w in result.warnings)


def boundaries(directory):
    project = directory / "project"
    project.mkdir()
    root = project / "main.tex"
    root.write_text("synthetic readonly source")
    output = project / ".latex_build"
    output.mkdir()
    denied = directory / "private"
    denied.write_text("synthetic external sentinel")
    (project / "external-link").symlink_to(denied)
    (output / "source-link").symlink_to(root)
    perl = r'''
use strict; use warnings; use JSON::PP; use IO::Socket::INET;
my ($source,$denied,$link,$output,$write_link,$port)=@ARGV;
sub opened { my ($p,$m)=@_; my $ok=open(my $f,$m,$p); close($f) if $ok; return $ok?1:0; }
my %r=(source_read=>opened($source,'<'), source_write=>opened($source,'>>'),
 external_read=>opened($denied,'<'), external_write=>opened($denied,'>>'),
 symlink_read=>opened($link,'<'), symlink_write=>opened($write_link,'>>'),
 output_write=>opened($output,'>'), unrelated_child=>(system('/usr/bin/true')==0?1:0),
 hardlink_source=>(link($source,$output.'.hardlink')?1:0));
my $s=IO::Socket::INET->new(PeerAddr=>'127.0.0.1',PeerPort=>$port,Proto=>'tcp',Timeout=>1);
$r{network}=$s?1:0; close($s) if $s;
print encode_json(\%r);
'''
    tools = detect_toolchain()
    command = tools.compile_command(root, output, LaTeXEngine.LUALATEX)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        with macos_sandbox_launch(command, toolchain=tools, engine=LaTeXEngine.LUALATEX,
                                 project_scope=project, root_file=root, output_dir=output) as launch:
            process = subprocess.run([*launch.command[:3], "/usr/bin/perl", "-e", perl,
                str(root), str(denied), str(project / "external-link"), str(output / "new"),
                str(output / "source-link"), str(listener.getsockname()[1])],
                env=launch.environment, cwd=project, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, close_fds=True, timeout=10)
    value = {"case": "boundaries", "returncode": process.returncode,
             "stdout": process.stdout, "stderr": process.stderr}
    if process.returncode == 0:
        value["checks"] = json.loads(process.stdout)
    write_report(directory, value)
    assert process.returncode == 0, value
    assert value["checks"] == {"source_read": 1, "output_write": 1, "source_write": 0,
        "external_read": 0, "external_write": 0, "symlink_read": 0,
        "symlink_write": 0, "unrelated_child": 0, "hardlink_source": 0, "network": 0}, value


async def stdio(directory):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    project, exports = directory / "project", directory / "exports"
    project.mkdir()
    exports.mkdir()
    root = project / "main.tex"
    root.write_text(r"\documentclass{article}\begin{document}Actual Mac MCP export.\end{document}")
    profile = project / PROFILE_PATH
    profile.parent.mkdir()
    profile.write_bytes(profile_bytes(ProjectProfile(engine="lualatex")))
    before = sha(root)
    parameters = StdioServerParameters(command=sys.executable,
        args=["-m", "app.mcp_server", "--project-root", str(project),
              "--allow-compile", "--export-root", str(exports)], cwd=str(REPO))
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            response = await session.call_tool("export_artifact", {"kind": "pdf", "target_path": "result.pdf"})
            value = {"case": "stdio", "is_error": response.is_error,
                     "response": response.model_dump(mode="json"), "source_unchanged": sha(root) == before}
            if not response.is_error:
                value["pdf_sha256"] = sha(exports / "result.pdf")
                value["text"] = subprocess.check_output(["pdftotext", str(exports / "result.pdf"), "-"], text=True)
            write_report(directory, value)
            assert not response.is_error and value["source_unchanged"], value
            assert "Actual Mac MCP export." in value["text"]
            assert response.structured_content["sha256"] == value["pdf_sha256"]


def cancellation(directory):
    root = directory / "main.tex"
    root.write_text(r'''\documentclass{article}
\begin{document}\directlua{local f=assert(io.open('build/ready','w')); f:write('ready'); f:close(); while true do end}\end{document}
''')
    completed = []
    manager = CompileManager(root, engine=LaTeXEngine.LUALATEX, restricted_io=True,
                             output_dir=directory / "build", on_finished=completed.append)
    manager.compile_async()
    deadline = time.monotonic() + 45
    # openout_any=p rejects explicit hidden path components even in the sandbox.
    # Use a non-hidden owned output for the readiness marker, not weaker policy.
    ready = directory / "build/ready"
    while not ready.exists() and time.monotonic() < deadline and not completed:
        time.sleep(0.05)
    if not ready.exists():
        manager.stop_current()
        write_report(directory, {"case": "cancellation", "ready": False,
            "completed": [{"outcome": r.outcome.value, "stdout": r.stdout, "stderr": r.stderr}
                          for r in completed]})
        raise AssertionError("actual Lua child did not reach readiness")
    with manager._lock:
        pid = manager._process.pid
    started = time.monotonic()
    stopped = manager.stop_current()
    idle = manager.wait_until_idle(5)
    try:
        os.killpg(pid, 0)
        group_gone = False
    except ProcessLookupError:
        group_gone = True
    value = {"case": "cancellation", "ready": True, "stopped": stopped, "idle": idle,
             "group_gone": group_gone, "seconds": time.monotonic() - started, "pid": pid}
    write_report(directory, value)
    assert stopped and idle and group_gone, value


def preexisting_hardlink(directory):
    project = directory / "project"
    project.mkdir()
    root = project / "main.tex"
    root.write_text("synthetic original")
    output = project / ".latex_build"
    output.mkdir()
    os.link(root, output / "preexisting-link")
    tools = detect_toolchain()
    command = tools.compile_command(root, output, LaTeXEngine.LUALATEX)
    try:
        with macos_sandbox_launch(command, toolchain=tools, engine=LaTeXEngine.LUALATEX,
                                 project_scope=project, root_file=root, output_dir=output) as launch:
            result = subprocess.run([*launch.command[:3], "/usr/bin/perl", "-e",
                "print open(my $f, '>>', $ARGV[0]) ? 'WRITABLE' : 'DENIED';", str(output / "preexisting-link")],
                cwd=project, env=launch.environment, capture_output=True, text=True, timeout=5)
            value = {"case": "preexisting-hardlink", "startup_refused": False,
                     "stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
    except OSError as exc:
        value = {"case": "preexisting-hardlink", "startup_refused": True, "reason": str(exc)}
    write_report(directory, value)
    assert value["startup_refused"], value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=("lua-bibtex", "lua-biber", "pdf", "xe", "boundaries", "stdio", "cancellation", "preexisting-hardlink"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    output = args.directory.resolve()
    output.mkdir(parents=True, exist_ok=False)
    before = identity()
    print(json.dumps({"source_sha256": before, "case": args.case}), flush=True)
    if args.case == "stdio":
        asyncio.run(stdio(output))
    elif args.case == "boundaries":
        boundaries(output)
    elif args.case == "cancellation":
        cancellation(output)
    elif args.case == "preexisting-hardlink":
        preexisting_hardlink(output)
    else:
        engine = {"lua-bibtex": LaTeXEngine.LUALATEX, "lua-biber": LaTeXEngine.LUALATEX, "pdf": LaTeXEngine.PDFLATEX,
                  "xe": LaTeXEngine.XELATEX}[args.case]
        compile_case(output, engine, bibliography=("biber" if args.case == "lua-biber" else args.case == "lua-bibtex"))
    assert identity() == before, "source changed during probe"


if __name__ == "__main__":
    main()
