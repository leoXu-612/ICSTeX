"""Read-only application audit using isolated, generated projects.

Run with QT_QPA_PLATFORM=offscreen python3 tools/bench_response_pipeline.py.
Only temporary synthetic projects and an explicitly named JSON report are
written. No application preference store or existing TeX project is used.
These timings are probes, not pass/fail performance thresholds.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from PySide6.QtCore import QEvent, QSettings, QTimer
from PySide6.QtGui import QImage, QTextCursor
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.core.asset_index import AssetIndex
from app.core.build_evidence import capture_compile_inputs
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.core.project_dependencies import static_dependencies
from app.core.settings import AppSettings
from app.core.word_count import count_project
from app.gui.main_window import MainWindow
from app.gui import dependency_controller


SENTENCE = "This sentence has ten words and includes another few tokens.\n"


def measure(call, repetitions: int = 5) -> dict:
    samples = []
    for _ in range(repetitions):
        started = time.perf_counter()
        call()
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "samples_ms": [round(value, 3) for value in samples],
        "median_ms": round(statistics.median(samples), 3),
        "max_ms": round(max(samples), 3),
    }


def wait_gui(predicate, timeout: float = 5) -> None:
    deadline = time.perf_counter() + timeout
    while not predicate() and time.perf_counter() < deadline:
        QApplication.processEvents()
        time.sleep(0.001)
    assert predicate(), "Asynchronous GUI operation timed out"


def document(repetitions: int = 400) -> str:
    return (
        "\\documentclass{article}\n\\begin{document}\n"
        + SENTENCE * repetitions
        + "\\end{document}\n"
    )


def word_count_probe(base: Path) -> list[dict]:
    results = []
    toolchain = detect_toolchain()
    for repetitions in (400, 1200, 4000):
        root = base / f"words-{repetitions}.tex"
        source = document(repetitions)
        root.write_text(source, encoding="utf-8")
        for mode, tools in (
            ("structured", replace(toolchain, texcount=None)),
            ("texcount", toolchain),
        ):
            result = count_project(root, {root: source}, tools)
            results.append({
                "words": result.words,
                "source_bytes": len(source.encode()),
                "requested_mode": mode,
                "actual_mode": result.source,
                **measure(lambda: count_project(root, {root: source}, tools)),
            })
    return results


def gui_probe(base: Path) -> dict:
    project = base / "gui"
    project.mkdir()
    root = project / "main.tex"
    child = project / "child.tex"
    bibliography = project / "refs.bib"
    source = document().replace(
        "\\end{document}",
        "\\input{child}\n\\bibliography{refs}\n\\end{document}",
    )
    root.write_text(source, encoding="utf-8")
    child.write_text("A child document.\n", encoding="utf-8")
    bibliography.write_text("@misc{example,title={Example}}\n", encoding="utf-8")
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(0xFF336699)
    assets = project / "assets"
    assets.mkdir()
    for index in range(50):
        assert image.save(str(assets / f"figure-{index}.png"))
    settings = AppSettings(QSettings(str(base / "probe.ini"), QSettings.Format.IniFormat))
    window = MainWindow(settings_store=settings)
    window.auto_compile_action.setChecked(False)
    window.project_files.set_project_root(project)
    window.open_file(root)
    tab = window.current_tab()
    assert tab is not None and tab.path == root
    # Opening a source intentionally does not create or authorize a compiler.
    # Register the manager explicitly without starting a TeX process.
    tab.manager = window.create_compile_manager(root)
    # Deterministic injected events below; no background observer races with
    # synthetic disk changes. Keep the registered watch set for inspection.
    window.file_watcher.stop()
    original_watch = window.file_watcher.watch
    window.file_watcher.watch = Mock()
    results = {}
    try:
        asynchronous = hasattr(window, "word_counts")
        if asynchronous:
            wait_gui(lambda: not window.word_counts.is_busy)
            dispatch = []
            completed = []
            for _ in range(5):
                started = time.perf_counter()
                window.update_word_count(force=True)
                dispatch.append((time.perf_counter() - started) * 1000)
                wait_gui(lambda: not window.word_counts.is_busy)
                completed.append((time.perf_counter() - started) * 1000)
        results = {
            "word_count": measure(window.update_word_count),
            "panel_refresh": measure(window.refresh_project_panels),
            "watched_files": sorted(path.relative_to(project).as_posix()
                                    for path in window.file_watcher._files),
            "unopened_child_watched": child.resolve() in window.file_watcher._files,
            "bibliography_watched": bibliography.resolve() in window.file_watcher._files,
        }
        if asynchronous:
            results["word_count_uncached_dispatch_ms"] = [round(value, 3) for value in dispatch]
            results["word_count_uncached_complete_ms"] = [round(value, 3) for value in completed]
            results["word_count_request_mode"] = "cached request; uncached dispatch/completion reported separately"
        for sidebar, label in ((0, "files"), (1, "outline")):
            window.sidebar_tabs.setCurrentIndex(sidebar)
            tab.editor.moveCursor(QTextCursor.MoveOperation.End)
            results[f"edit_with_{label}_sidebar"] = measure(
                lambda: tab.editor.insertPlainText("x"), 15,
            )
            window.documents.cancel_save_timer(tab)

        if hasattr(window, "project_panels"):
            # Keep the original hidden-window metric above for comparison;
            # measure the genuinely visible dock as a separate new case.
            window.show()
            window.set_toolbox_visible(True)
            window.sidebar_tabs.setCurrentIndex(1)
            QApplication.processEvents()
            window.project_panels.refresh_visible()
            with patch.object(window.outline_panel, "set_outline", wraps=window.outline_panel.set_outline) as outline, \
                 patch.object(AssetIndex, "scan", autospec=True) as scan:
                results["edit_with_visible_outline"] = measure(lambda: tab.editor.insertPlainText("x"), 15)
                results["outline_updates_during_edit_burst"] = outline.call_count
                window.documents.cancel_save_timer(tab)
                wait_gui(lambda: not window.project_panels._timer.isActive())
                results["outline_updates_after_debounce"] = outline.call_count
                results["asset_scans_for_text_edit_burst"] = scan.call_count
            window.hide()

        # One GUI timer cannot run while the synchronous word count callback
        # is executing. This measures event-loop delay, not rendered frames.
        heartbeat = []
        started = time.perf_counter()
        QTimer.singleShot(0, lambda: window.update_word_count(force=True) if asynchronous else window.update_word_count())
        QTimer.singleShot(10, lambda: heartbeat.append(time.perf_counter()))
        while not heartbeat and time.perf_counter() - started < 5:
            QApplication.processEvents()
        assert heartbeat, "GUI heartbeat timed out"
        results["word_count_timer_lateness_ms"] = round(
            max(0, (heartbeat[0] - started) * 1000 - 10), 3,
        )
        if asynchronous:
            wait_gui(lambda: not window.word_counts.is_busy)

        tab.modified = False
        tab.dirty = False
        window.documents.cancel_save_timer(tab)
        window.compile_authorized_roots.add(tab.manager.root_file)
        root.write_text(source.replace("This sentence", "An external sentence", 1), encoding="utf-8")
        with patch.object(tab.manager, "schedule_compile") as scheduled:
            window.documents.reload_external_change(str(root))
            results["external_tex_auto_off_scheduled_count"] = scheduled.call_count
        results["external_tex_auto_toggle"] = window.auto_compile_action.isChecked()
        results["external_tex_reloaded"] = "An external sentence" in tab.editor.toPlainText()
        if asynchronous:
            wait_gui(lambda: not window.word_counts.is_busy)

        # Additional V1 case, separate from the unchanged M0 timing samples.
        # Wrappers observe real work; they do not replace its implementation.
        window.show()
        window.readiness.show()
        wait_gui(lambda: not window.readiness.is_busy and not window.word_counts.is_busy
                 and not window.dependencies.is_busy)
        with patch.object(window.readiness, "_launch", wraps=window.readiness._launch) as checks, \
             patch.object(window.word_counts, "_launch", wraps=window.word_counts._launch) as counts, \
             patch.object(dependency_controller, "static_dependencies",
                          wraps=dependency_controller.static_dependencies) as dependencies, \
             patch.object(AssetIndex, "scan", autospec=True, side_effect=AssetIndex.scan) as scans:
            burst = measure(lambda: tab.editor.insertPlainText("x"), 15)
            window.documents.cancel_save_timer(tab)
            immediate = {"checks": checks.call_count, "word_counts": counts.call_count,
                         "dependencies": dependencies.call_count, "assets": scans.call_count}
            assert not any(immediate.values()), immediate
            wait_gui(lambda: not window.dependencies.is_busy and not window.word_counts.is_busy
                     and not window.project_panels._timer.isActive())
            after = {"checks": checks.call_count, "word_counts": counts.call_count,
                     "dependencies": dependencies.call_count, "assets": scans.call_count}
            assert after["checks"] == after["assets"] == 0, after
            results["edit_with_submission_check_visible"] = {
                **burst, "immediate_work_calls": immediate, "after_debounce_work_calls": after,
                "check_result_invalidated": window.readiness._displayed_key is None,
            }
        return results
    finally:
        window.file_watcher.watch = original_watch
        for open_tab in window.tabs.values():
            window.documents.cancel_save_timer(open_tab)
            open_tab.modified = False
            open_tab.dirty = False
        assert window.close(), "Synthetic clean window refused close"
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert not isValid(window), "Accepted window retained its Qt object"
        results["closed_window_destroyed"] = True
        QApplication.processEvents()


def asset_scan_probe(base: Path) -> list[dict]:
    project = base / "scan"
    project.mkdir()
    index = AssetIndex(project)
    results = [{"ignored_files": 0, **measure(index.scan)}]
    ignored = project / ".latex_build" / "nested"
    ignored.mkdir(parents=True)
    for number in range(5000):
        (ignored / f"artifact-{number}.tmp").touch()
    results.append({"ignored_files": 5000, **measure(index.scan)})
    return results


def dependency_probe(base: Path) -> list[dict]:
    results = []
    for children in (10, 50, 200):
        project = base / f"dependencies-{children}"
        project.mkdir()
        root = project / "main.tex"
        root.write_text("".join(f"\\input{{child-{i}.tex}}\n" for i in range(children)), encoding="utf-8")
        for number in range(children):
            (project / f"child-{number}.tex").write_text(SENTENCE * (400 // children), encoding="utf-8")
        graph = static_dependencies(root, project)
        snapshot = capture_compile_inputs(root, project)
        assert graph.complete and snapshot.complete
        assert len(graph.paths) == len(snapshot.observations) == children + 1
        original = {path: path.read_bytes() for path in graph.paths}
        results.append({
            "children": children, "files": len(graph.paths),
            "source_bytes": sum(map(len, original.values())),
            "static_graph": measure(lambda: static_dependencies(root, project)),
            "graph_and_content_hashes": measure(lambda: capture_compile_inputs(root, project)),
            "cache_condition": "Repeated reads; OS cache not flushed; no app graph cache",
        })
        assert all(path.read_bytes() == data for path, data in original.items())
    return results


def compile_probe(base: Path, purpose: BuildPurpose = BuildPurpose.FINAL) -> list[dict]:
    tools = detect_toolchain()
    if not tools.latexmk or not tools.xelatex:
        return [{"skipped": "latexmk and xelatex required; no installation attempted"}]
    results = []
    for trial in range(3):
        project = base / f"compile-{purpose.value}-{trial}"
        project.mkdir()
        root = project / "main.tex"
        source = (
            "\\documentclass{article}\n\\usepackage{fontspec}\n"
            "\\begin{document}\n\\tableofcontents\n"
            "\\section{Probe}\\label{sec:probe}\n"
            "Section \\ref{sec:probe}. Citation \\cite{example}.\n"
            + SENTENCE * 400
            + "\\bibliographystyle{plain}\n\\bibliography{refs}\n\\end{document}\n"
        )
        root.write_text(source, encoding="utf-8")
        (project / "refs.bib").write_text(
            "@misc{example,author={Example Author},title={Synthetic benchmark},year={2026}}\n",
            encoding="utf-8",
        )
        manager = CompileManager(root, toolchain=tools, engine=LaTeXEngine.XELATEX)
        previous_hash = None
        for label in ("cold", "unchanged", "identical_rewrite", "text_edit"):
            if label == "identical_rewrite":
                root.write_text(source, encoding="utf-8")
            elif label == "text_edit":
                root.write_text(source.replace("This sentence", "The sentence", 1), encoding="utf-8")
            started = time.perf_counter()
            result = manager.compile_now(purpose, timeout_seconds=60)
            call_ms = (time.perf_counter() - started) * 1000
            assert result is not None and result.ok, (label, result)
            digest = hashlib.sha256(result.pdf_file.read_bytes()).hexdigest()
            pdf = QPdfDocument()
            error = pdf.load(str(result.pdf_file))
            pages = pdf.pageCount()
            assert error == QPdfDocument.Error.None_ and pages > 0, (error, pages)
            pdf.close()
            results.append({
                "trial": trial,
                "case": label,
                "purpose": result.purpose.value,
                "duration_ms": round(result.duration_seconds * 1000, 3),
                "call_ms": round(call_ms, 3),
                "forced_rebuild": "-g" in result.command,
                "input_evidence_stable": bool(result.input_evidence and result.input_evidence.stable),
                "rules": re.findall(r"Run number \d+ of rule '([^']+)'", result.stdout),
                "pages": pages,
                "pdf_bytes": result.pdf_file.stat().st_size,
                "same_pdf_bytes_as_previous": previous_hash == digest,
                "safe_command": "-norc" in result.command and "-no-shell-escape" in result.command,
            })
            previous_hash = digest
        assert manager.retire(), "Synchronous benchmark manager did not retire"
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sections", nargs="+", choices=("word_count", "gui", "asset_scan", "dependencies", "compile", "preview"))
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    app_digest = hashlib.sha256()
    for source in sorted((REPO / "app").rglob("*.py")):
        app_digest.update(source.relative_to(REPO).as_posix().encode())
        app_digest.update(b"\0")
        app_digest.update(source.read_bytes())
        app_digest.update(b"\0")
    report = {
        "app_python_tree_sha256": app_digest.hexdigest(),
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True,
        ).strip(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "pyside6": importlib.metadata.version("PySide6"),
            "watchdog": importlib.metadata.version("watchdog"),
        },
        "scope": "Synthetic temporary projects; synchronous call and event-loop timings, not rendered-frame latency",
    }
    with TemporaryDirectory(prefix="icstex-response-probe-") as directory:
        base = Path(directory).resolve()
        for name, probe in (
            ("word_count", word_count_probe),
            ("gui", gui_probe),
            ("asset_scan", asset_scan_probe),
            ("dependencies", dependency_probe),
            ("compile", compile_probe),
            ("preview", lambda base: compile_probe(base, BuildPurpose.PREVIEW)),
        ):
            if args.sections and name not in args.sections:
                continue
            print(f"Probing {name}...", file=sys.stderr, flush=True)
            report[name] = probe(base)
    post_digest = hashlib.sha256()
    for source in sorted((REPO / "app").rglob("*.py")):
        post_digest.update(source.relative_to(REPO).as_posix().encode() + b"\0" + source.read_bytes() + b"\0")
    assert post_digest.hexdigest() == report["app_python_tree_sha256"], "Shared app source changed during measurement"
    report["app_hash_matches_after_run"] = True
    report["compile_comparison_boundary"] = (
        "FINAL now forces TeX work; old warm FINAL with no latexmk rules is not equivalent. "
        "PREVIEW uses a separate output tree here with original inputs and no image proxy preparer."
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    app.processEvents()


if __name__ == "__main__":
    main()
