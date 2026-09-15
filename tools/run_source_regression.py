"""Run the required unittest command with an untruncated local receipt."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preflight", action="store_true", help="Run packaging preflight, which includes the required source tests")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    from tools.bench_pdf_pipeline import source_digest
    from tools.probe_macos_compiler_sandbox import identity
    before = {"app": source_digest(), "app_tests": identity()}
    command = (["bash", "packaging/preflight.sh"] if args.preflight else
               [sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    log = output / ("preflight.log" if args.preflight else "unittest.log")
    started = time.perf_counter()
    print(f"Running required validation; full output: {log}", flush=True)
    with log.open("xb") as stream:
        result = subprocess.run(command, cwd=REPO, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                                stdout=stream, stderr=subprocess.STDOUT)
    after = {"app": source_digest(), "app_tests": identity()}
    receipt = {"command": command, "exit_code": result.returncode,
               "elapsed_seconds": time.perf_counter() - started, "before": before, "after": after,
               "unchanged_source": before == after, "passed": result.returncode == 0 and before == after}
    (output / "result.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    print(log.read_text(errors="replace")[-6000:])
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
