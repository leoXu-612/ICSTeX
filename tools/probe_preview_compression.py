"""Compare lossless PDF compression using one frozen XDV, never source edits."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    xdv = args.xdv.resolve()
    digest = hashlib.sha256(xdv.read_bytes()).hexdigest()
    rows = []
    first_level, second_level = args.levels
    for level in (first_level, second_level, second_level, first_level, first_level, second_level):
        pdf = output / f"level-{level}.pdf"
        command = ["/Library/TeX/texbin/xdvipdfmx", "-E", "-z", str(level), "-o", str(pdf), str(xdv)]
        started = time.perf_counter()
        result = subprocess.run(command, cwd=args.project, capture_output=True, timeout=45)
        elapsed = (time.perf_counter() - started) * 1000
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        rows.append({"level": level, "ms": elapsed, "bytes": pdf.stat().st_size})
        print(rows[-1], flush=True)
    # Decode every page identically: compressed stream bytes must not alter pixels.
    for level in args.levels:
        subprocess.run(["pdftoppm", "-r", "72", "-png", str(output / f"level-{level}.pdf"),
                        str(output / f"level-{level}")], check=True, capture_output=True, timeout=60)
    first = sorted(output.glob(f"level-{first_level}-*.png"))
    second = sorted(output.glob(f"level-{second_level}-*.png"))
    assert len(first) == len(second) and len(first) > 0
    equal = all(a.read_bytes() == b.read_bytes() for a, b in zip(first, second))
    report = {"xdv_sha256": digest, "samples": rows,
              "median_ms": {level: statistics.median(row["ms"] for row in rows if row["level"] == level)
                            for level in args.levels},
              "pages": len(first), "all_rendered_pages_equal": equal,
              "xdv_unchanged": digest == hashlib.sha256(xdv.read_bytes()).hexdigest()}
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)
    assert equal and report["xdv_unchanged"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xdv", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--levels", nargs=2, type=int, choices=range(10), default=(9, 1))
    run(parser.parse_args())
