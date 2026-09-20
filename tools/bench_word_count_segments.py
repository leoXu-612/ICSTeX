"""Bounded E1 comparison of real counting and exact visual-segment results.

No QApplication or TeX compilation is started. Inputs are synthetic, the output
directory must be new, and TeXcount uses the application's unchanged local path.
"""
from __future__ import annotations

import argparse
import cProfile
import gc
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import pstats
import statistics
import subprocess
import sys
import time
import tracemalloc

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.core.latex_tools import detect_toolchain
from app.core.word_count import count_project
from tools.bench_response_pipeline import document
from tools.bench_pdf_pipeline import source_digest


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def fixtures(base):
    cases = []
    for size in (4000, 12000, 40000):
        for kind in ("english", "chinese", "mixed-multi-draft"):
            home = base / f"{kind}-{size}"
            home.mkdir(parents=True)
            root = home / "main.tex"
            if kind == "english":
                source = document(size // 10)  # Same English input as the A probe.
            elif kind == "chinese":
                chars = ("\u4e2d\u6587\u5199\u4f5c\u6d4b\u8bd5" * (size // 6 + 1))[:size]
                source = "\\documentclass{article}\n\\begin{document}\n" + chars + "\n\\end{document}\n"
            else:
                source = ("\\documentclass{article}\n\\title{Synthetic title}\n\\begin{document}\n"
                    "\\maketitle\\section{Heading 2026}Root words.\n"
                    "\\input{intro}\\input{body}\\input{intro}\n"
                    "\\bibliographystyle{plain}\\bibliography{refs}\n\\end{document}\n")
                (home / "intro.tex").write_text("Introduction \u4e2d\u6587\u3002\\footnote{A note 3.5}\\cite{sample}\n")
                packet = ("Text \u4e2d\u6587\u8ba1\u6570 12.5 units. \\textbf{Bold words} $x^2$. "
                          "\\begin{equation}a=b\\end{equation}\n")
                (home / "body.tex").write_text(packet * (size // 20) +
                    "%TC:ignore\nIgnored words 999 \u4e2d\u6587\n%TC:endignore\n", encoding="utf-8")
                (home / "refs.bib").write_text("@misc{sample,title={Synthetic bibliography excluded}}\n")
            root.write_text(source, encoding="utf-8")
            overrides = {root: source}
            if kind == "mixed-multi-draft":
                child = home / "body.tex"
                overrides[child] = child.read_text(encoding="utf-8") + "\nUnsaved child draft \u4e2d\u6587\u3002\n"
            cases.append((f"{kind}-{size}", root, overrides))
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--profile-only", action="store_true")
    parser.add_argument("--paired-reference", type=Path,
                        help="Exact pre-change word_count.py snapshot; used for one interleaved 40k fallback check")
    parser.add_argument("--paired-case", default="english-40000")
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 30:
        raise ValueError("Use 1..30 bounded repetitions")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    tools = detect_toolchain()
    if not tools.texcount:
        raise RuntimeError("TeXcount unavailable; do not install a runtime for this probe")
    version = subprocess.run([tools.texcount, "-version"], capture_output=True, text=True, timeout=10)
    baseline = json.loads(args.baseline.read_text()) if args.baseline else None
    expected = {(row["fixture"], row["mode"]): row for row in baseline["rows"]} if baseline else {}
    report = {"completed": False, "app_sha256": source_digest(), "rows": [], "unmeasured": [],
        "environment": {"platform": platform.platform(), "python": platform.python_version(),
                        "texcount": tools.texcount, "texcount_version": version.stdout.strip()},
        "measurement": "count_project synchronous return; one untimed primer then samples; no GUI/render/TeX-engine timing",
        "cpu_boundary": "parent Python CPU only; TeXcount child CPU is excluded",
        "percentiles": "median and all samples; no p95 claim from five samples",
        "repetitions": args.repetitions, "baseline": str(args.baseline) if args.baseline else None}
    cases = fixtures(output / "fixtures")
    files = {p: p.read_bytes() for p in (output / "fixtures").rglob("*") if p.is_file()}
    report["fixture_sha256"] = digest({p.relative_to(output / "fixtures").as_posix():
        hashlib.sha256(data).hexdigest() for p, data in files.items()})
    if baseline:
        assert report["fixture_sha256"] == baseline["fixture_sha256"], "Fixture bytes changed"
    try:
        for name, root, overrides in (() if args.profile_only else cases):
            for mode, toolchain in (("fallback", replace(tools, texcount=None)), ("texcount", tools)):
                if baseline and (name, mode) not in expected:
                    report["unmeasured"].append({"fixture": name, "mode": mode,
                        "reason": "No completed timing row in the baseline; do not repeat its failing stress case"})
                    continue
                call = lambda: count_project(root, overrides, toolchain)
                reference = call()
                raw = asdict(reference)
                result_hash = digest(raw)
                (output / f"{name}-{mode}-result.json").write_text(
                    json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                if reference.source != mode:
                    report["unmeasured"].append({"fixture": name, "mode": mode,
                        "actual_mode": reference.source, "result_sha256": result_hash,
                        "reason": "Requested mode fell back; preserve the result, do not repeat the timeout"})
                    continue
                samples, cpu = [], []
                for _ in range(args.repetitions):
                    started, cpu_started = time.perf_counter(), time.process_time()
                    result = call()
                    cpu.append((time.process_time() - cpu_started) * 1000)
                    samples.append((time.perf_counter() - started) * 1000)
                    assert result == reference, "Repeated result differs"
                row = {"fixture": name, "mode": mode, "result_sha256": result_hash,
                    "actual_mode": reference.source, "words": reference.total_words,
                    "segments": len(reference.visual_segments),
                    "samples_ms": [round(value, 3) for value in samples],
                    "parent_cpu_ms": [round(value, 3) for value in cpu],
                    "median_ms": round(statistics.median(samples), 3)}
                report["rows"].append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
                if baseline:
                    previous = expected[(name, mode)]
                    assert result_hash == previous["result_sha256"], (name, mode, "Full result differs from baseline")
                    row["median_reduction_percent"] = round(100 * (1 - row["median_ms"] / previous["median_ms"]), 2)
        name, root, overrides = next(case for case in cases if case[0] == "english-40000")
        fallback = replace(tools, texcount=None)
        if args.paired_reference:
            paired_name, paired_root, paired_overrides = next(case for case in cases if case[0] == args.paired_case)
            spec = importlib.util.spec_from_file_location("app.core._word_count_reference", args.paired_reference)
            reference = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = reference
            spec.loader.exec_module(reference)
            calls = {"before": lambda: reference.count_project(paired_root, paired_overrides, fallback),
                     "after": lambda: count_project(paired_root, paired_overrides, fallback)}
            assert asdict(calls["before"]()) == asdict(calls["after"]())
            pairs = []
            for index in range(args.repetitions):
                values, results = {}, {}
                for label in (("before", "after") if index % 2 == 0 else ("after", "before")):
                    started = time.perf_counter()
                    results[label] = calls[label]()
                    values[label] = round((time.perf_counter() - started) * 1000, 3)
                assert asdict(results["before"]) == asdict(results["after"])
                pairs.append(values)
            report["paired_comparison"] = {"fixture": paired_name, "samples_ms": pairs,
                "reference_sha256": hashlib.sha256(args.paired_reference.read_bytes()).hexdigest(),
                "method": "same process/input, alternating order; exact full-result equality each pair"}
            allocation_pairs = {}
            for label, call in calls.items():
                gc.collect()
                tracemalloc.start()
                allocated_result = call()
                current, peak = tracemalloc.get_traced_memory()
                del allocated_result
                gc.collect()
                released, _ = tracemalloc.get_traced_memory()
                tracemalloc.stop()
                allocation_pairs[label] = {"current_bytes": current, "peak_bytes": peak,
                                           "after_result_release_and_gc_bytes": released}
            report["allocation_diagnostic"] = {"fixture": paired_name, "results": allocation_pairs,
                "boundary": "isolated diagnostic with explicit GC before/after; no application GC policy or RSS claim"}
        profiler = cProfile.Profile()
        profiler.runcall(count_project, root, overrides, fallback)
        profiler.dump_stats(str(output / "english-40000-profile.pstats"))
        stats = pstats.Stats(profiler)
        profile = [{"file": file, "line": line, "function": function, "calls": values[1],
                    "self_seconds": values[2], "cumulative_seconds": values[3]}
                   for (file, line, function), values in stats.stats.items()]
        report["profile"] = sorted(profile, key=lambda item: item["cumulative_seconds"], reverse=True)[:45]
        tracemalloc.start()
        result = count_project(root, overrides, fallback)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        report["python_allocations"] = {"current_bytes": current, "peak_bytes": peak,
            "boundary": "one warm 40k English fallback call; traced Python allocations, not process RSS or leak evidence"}
    except BaseException as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["inputs_unchanged"] = all(path.read_bytes() == payload for path, payload in files.items())
        report["app_sha256_after"] = source_digest()
        report["completed"] = (not report.get("error") and report["inputs_unchanged"]
            and report["app_sha256"] == report["app_sha256_after"])
        (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert report["completed"], report
    print(json.dumps({key: report[key] for key in ("completed", "app_sha256", "python_allocations")}), flush=True)


if __name__ == "__main__":
    main()
