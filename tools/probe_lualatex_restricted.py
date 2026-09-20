"""Diagnose installed LuaLaTeX using synthetic inputs and unchanged restricted IO.

Never installs packages, changes TeX configuration or enables shell escape.
A successful probe means its observations were captured, not that LuaLaTeX works.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from tools.probe_history_restore import app_digest


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(output: Path, *, verify_gui: bool = False):
    output = output.resolve()
    output.mkdir(exist_ok=False)
    before = app_digest()
    toolchain = detect_toolchain()
    assert toolchain.lualatex, "Existing LuaLaTeX required; no installation attempted"
    texbin = Path(toolchain.lualatex).parent
    kpsewhich = texbin / "kpsewhich"
    luahbtex = texbin / "luahbtex"
    report = {"synthetic_only": True, "app_sha256": before,
              "platform": platform.platform(), "python": platform.python_version(),
              "toolchain": {key: getattr(toolchain, key) for key in ("latexmk", "pdflatex", "xelatex", "lualatex")},
              "compile": [], "resource_checks": []}
    source = ("\\documentclass{article}\n\\begin{document}\n"
              "Restricted engine synthetic test. $E=mc^2$.\n\\end{document}\n")
    for engine in (LaTeXEngine.PDFLATEX, LaTeXEngine.XELATEX, LaTeXEngine.LUALATEX):
        project = output / engine.value
        project.mkdir()
        root = project / "main.tex"
        root.write_text(source, encoding="utf-8")
        manager = CompileManager(root, engine=engine, restricted_io=True)
        result = manager.compile_now(BuildPurpose.FINAL, timeout_seconds=30)
        assert result is not None
        assert root.read_text(encoding="utf-8") == source
        assert "-no-shell-escape" in result.command
        if toolchain.latexmk:
            assert "-norc" in result.command
        (output / f"{engine.value}.stdout.log").write_text(result.stdout, encoding="utf-8")
        (output / f"{engine.value}.stderr.log").write_text(result.stderr, encoding="utf-8")
        value = {"engine": engine.value, "ok": result.ok, "outcome": result.outcome.value,
                 "returncode": result.returncode, "command": result.command,
                 "errors": [{"message": error.message, "file": str(error.file) if error.file else None,
                             "line": error.line} for error in result.errors],
                 "source_unchanged": True, "source_sha256": sha(root.read_bytes()),
                 "pdf_sha256": sha(result.pdf_file.read_bytes()) if result.pdf_file.exists() else None}
        report["compile"].append(value)
        print(json.dumps(value), flush=True)

    project = output / "raw-lua"
    project.mkdir()
    root = project / "probe.tex"
    # This invokes primitive LuaTeX without the failing LaTeX font-loader setup.
    # Read-only checks contrast TeX-distribution paths with an identical local
    # resource copy and an out-of-project synthetic sentinel, never user files.
    lua_source = r'''\catcode123=1 \catcode125=2
\directlua0{
local function check(label, path)
  local f, err = io.open(path, "r")
  texio.write_nl("term and log", "PROBE " .. label .. " path=" .. tostring(path) .. " open=" .. tostring(f ~= nil) .. " error=" .. tostring(err))
  if f then f:close() end
end
check("distribution", kpse.find_file("ScriptExtensions.txt"))
check("local-copy", "local-copy.txt")
check("parent-sentinel", "../sentinel.txt")
texio.write_nl("term and log", "PROBE shell_escape=" .. tostring(status.shell_escape))
}
\end
'''
    root.write_text(lua_source, encoding="utf-8")
    manager = CompileManager(root, engine=LaTeXEngine.LUALATEX, restricted_io=True)
    env = manager._compile_environment(None, restricted_io=True)
    assert env["openin_any"] == env["openout_any"] == "p"
    found = subprocess.run([str(kpsewhich), "ScriptExtensions.txt"], env=env,
                           capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    resource = Path(found)
    assert resource.is_absolute() and resource.is_file()
    assert resource.stat().st_size < 1024 * 1024
    raw = resource.read_bytes()
    (project / "local-copy.txt").write_bytes(raw)
    sentinel = output / "sentinel.txt"
    sentinel.write_text("Synthetic out-of-project sentinel\n", encoding="utf-8")
    for name in (str(resource), "local-copy.txt", "../sentinel.txt"):
        check = subprocess.run([str(kpsewhich), "-safe-extended-in-name=" + name], cwd=project,
                               env=env, capture_output=True, text=True, timeout=10)
        report["resource_checks"].append({"name": name, "returncode": check.returncode,
                                          "stdout": check.stdout, "stderr": check.stderr})
    command = [str(luahbtex), "--ini", "--no-shell-escape", "--nosocket", "--interaction=nonstopmode",
               "--halt-on-error", "--recorder", "probe.tex"]
    observed = subprocess.run(command, cwd=project, env=env, capture_output=True, text=True, timeout=30)
    (output / "raw-lua.stdout.log").write_text(observed.stdout, encoding="utf-8")
    (output / "raw-lua.stderr.log").write_text(observed.stderr, encoding="utf-8")
    report["raw_lua"] = {"command": command, "returncode": observed.returncode,
                          "stdout": observed.stdout, "stderr": observed.stderr,
                          "restricted_environment": {key: env[key] for key in ("openin_any", "openout_any")},
                          "resource_sha256": sha(raw)}
    assert resource.read_bytes() == raw
    assert (project / "local-copy.txt").read_bytes() == raw
    assert sentinel.read_text(encoding="utf-8") == "Synthetic out-of-project sentinel\n"
    assert root.read_text(encoding="utf-8") == lua_source
    if verify_gui:
        from PySide6.QtWidgets import QApplication
        from app.core.compiler import CompileOutcome
        from app.gui.theme import apply_theme
        from tools.probe_project_checkpoint_gui import close, window_for
        from tools.probe_submission_check import wait_for

        application = QApplication.instance() or QApplication([])
        assert application.platformName() == "offscreen", "This optional UI check is background-only"
        apply_theme(application)
        window = window_for(output, "lua-diagnostic")
        gui_project = output / "gui-case"
        gui_project.mkdir()
        gui_root = gui_project / "main.tex"
        gui_root.write_text(source, encoding="utf-8")
        try:
            window.project_files.set_project_root(gui_project)
            window.open_file(gui_root)
            window.compile.set_engine(LaTeXEngine.LUALATEX, compile_after=False)
            # Exercise the observed protected/Agent failure in the existing
            # GUI result pipeline; do not change the GUI's default I/O policy.
            window.current_tab().manager.restricted_io = True
            window.show()
            application.processEvents()
            editor = window.current_tab().editor
            position = (editor.textCursor().position(), editor.verticalScrollBar().value())
            window.compile_action.trigger()
            wait_for(lambda: window.pdf_state.record_for(gui_root).last_outcome == CompileOutcome.LATEX_ERROR, seconds=30)
            wait_for(lambda: not window.workspace._timer.isActive()
                     and "\u6b63\u5728\u7f16\u8bd1" not in window.workspace.details.full_text)
            diagnostics = window.diagnostic_panel.diagnostics
            assert len(diagnostics) == 1 and diagnostics[0].title == "LuaLaTeX \u5b57\u4f53\u7ec4\u4ef6\u5931\u8d25"
            assert "multiscript.lua:70: attempt to index a nil value" in diagnostics[0].raw_message
            assert diagnostics[0].file is None and diagnostics[0].line is None and diagnostics[0].fix is None
            assert not window.diagnostic_panel.fix_button.isEnabled()
            assert window.bottom_tabs.currentWidget() is window.diagnostic_panel
            assert editor.toPlainText() == source and gui_root.read_text(encoding="utf-8") == source
            assert (editor.textCursor().position(), editor.verticalScrollBar().value()) == position
            assert window.current_engine == LaTeXEngine.LUALATEX
            assert window.current_tab().manager.restricted_io
            window.vertical_splitter.setSizes([440, 310])
            application.processEvents()
            # Expand columns/rows in this inspection fixture to expose the
            # whole explanation; do not change production layout defaults.
            table = window.diagnostic_panel.table
            table.setColumnWidth(0, 65)
            table.setColumnWidth(1, 195)
            table.setColumnWidth(2, 55)
            table.resizeRowsToContents()
            application.processEvents()
            assert table.viewport().rect().contains(table.visualItemRect(table.item(0, 3)))
            assert window.grab().save(str(output / "diagnostic-window.png"))
            report["gui"] = {"qt_platform": application.platformName(), "title": diagnostics[0].title,
                             "message": diagnostics[0].message, "raw_message": diagnostics[0].raw_message,
                             "settled_workspace": window.workspace.details.full_text,
                             "diagnostic_row_visible": True,
                             "no_source_fix_or_location": True, "source_cursor_scroll_unchanged": True,
                             "engine_and_restricted_policy_unchanged": True}
        finally:
            close(window)
    report["app_sha256_after"] = app_digest()
    assert report["app_sha256_after"] == before
    report["limits"] = "Installed engine/resource checks; no unrestricted compile, package repair or native GUI acceptance"
    report["observations_complete"] = observed.returncode == 0 and all(
        "PROBE " + label in observed.stdout for label in ("distribution", "local-copy", "parent-sentinel", "shell_escape"))
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    assert report["observations_complete"], "Raw Lua diagnostic incomplete; see report.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-gui", action="store_true")
    args = parser.parse_args()
    run(args.output, verify_gui=args.verify_gui)
