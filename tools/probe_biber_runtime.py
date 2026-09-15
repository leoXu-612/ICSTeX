"""One-shot Biber startup diagnosis with owned temporary state, no TeX input."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.core.macos_compiler_sandbox import macos_sandbox_launch
from tools.probe_macos_compiler_sandbox import identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--dependencies-only", action="store_true")
    args = parser.parse_args()
    output = args.directory.resolve()
    output.mkdir(exist_ok=False)
    project = output / "project"
    project.mkdir()
    root = project / "main.tex"
    root.write_text("synthetic placeholder; never compiled")
    build = project / ".latex_build"
    build.mkdir()
    toolchain = detect_toolchain()
    assert toolchain.biber
    command = toolchain.compile_command(root, build, LaTeXEngine.LUALATEX)
    report = {"app_tests_sha256": identity(),
              "biber_sha256": hashlib.sha256(Path(toolchain.biber).read_bytes()).hexdigest(),
              "cases": []}
    with macos_sandbox_launch(command, toolchain=toolchain, engine=LaTeXEngine.LUALATEX,
                             project_scope=project, root_file=root, output_dir=build) as launch:
        # Startup control: installed trusted binary with --version only, no
        # document input, same clean environment and disposable cache directory.
        cases = (
            [("sandboxed-xcode-select", launch.command[:3], ["/usr/bin/xcode-select", "-p"]),
             ("sandboxed-lipo", launch.command[:3], ["/usr/bin/lipo", "-archs", toolchain.biber])]
            if args.dependencies_only else
            [("unconfined-version-control", [], [toolchain.biber, "--version"]),
             ("sandboxed-version", launch.command[:3], [toolchain.biber, "--version"])]
        )
        for label, prefix, child_command in cases:
            started = time.monotonic()
            result = subprocess.run([*prefix, *child_command],
                cwd="/", env=launch.environment, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=30, close_fds=True)
            item = {"case": label, "returncode": result.returncode,
                    "seconds": time.monotonic() - started, "stdout": result.stdout, "stderr": result.stderr}
            report["cases"].append(item)
            print(json.dumps(item), flush=True)
        report["temporary_files"] = sorted(str(p.relative_to(Path(launch.environment["TMPDIR"])))
            for p in Path(launch.environment["TMPDIR"]).rglob("*") if p.is_file())
    assert identity() == report["app_tests_sha256"]
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
