"""Diagnose the E1 synthetic stress fallback once, with the production timeout."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.core.word_count as word_count
from app.core.latex_tools import detect_toolchain
from tools.bench_pdf_pipeline import source_digest
from tools.bench_word_count_segments import fixtures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    cases = fixtures(output / "fixtures")
    name, root, overrides = next(case for case in cases if case[0] == "mixed-multi-draft-40000")
    original = {p: p.read_bytes() for p in (output / "fixtures").rglob("*") if p.is_file()}
    report = {"app_sha256": source_digest(), "fixture": name, "subprocess_events": []}
    run = word_count.subprocess.run

    def observed_run(*args, **kwargs):
        started = time.perf_counter()
        event = {"timeout_seconds": kwargs.get("timeout")}
        try:
            result = run(*args, **kwargs)
            event["returncode"] = result.returncode
            return result
        except Exception as exc:
            event["exception"] = type(exc).__name__
            raise
        finally:
            event["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            report["subprocess_events"].append(event)

    tools = detect_toolchain()
    assert tools.texcount, "No runtime installation is authorized"
    with patch("app.core.word_count.subprocess.run", observed_run):
        result = word_count.count_project(root, overrides, tools)
    report.update(actual_mode=result.source, warnings=result.warnings, words=result.total_words,
                  inputs_unchanged=all(p.read_bytes() == raw for p, raw in original.items()),
                  app_sha256_after=source_digest())
    report["completed"] = report["inputs_unchanged"] and report["app_sha256"] == report["app_sha256_after"]
    (output / "count-result.json").write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n")
    (output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    assert report["completed"]


if __name__ == "__main__":
    main()
