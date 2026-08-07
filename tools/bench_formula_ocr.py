"""Formula OCR accuracy benchmark (fixtures + real model inference).

Renders LaTeX formulas to PNG fixtures (xelatex + sips), then, when
ICSTEX_PIX2TEX_ENV points at an installed pix2tex venv, runs the real model
over each image and records outputs + timing to
docs/data/formula-ocr-benchmark.csv.  Plain text labels are recorded next to
the expected LaTeX for manual review (semantic equivalence is not computed
automatically).
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "formula_ocr" / "generated"
OUT_CSV = ROOT / "docs" / "data" / "formula-ocr-benchmark.csv"

FORMULAS = [
    ("simple_inline", r"E=mc^2"),
    ("simple_poly", r"x^2+1"),
    ("fraction", r"\frac{a}{b}"),
    ("fraction_nested", r"\frac{x^2+1}{\sqrt{y}}"),
    ("root", r"\sqrt{y_1+y_2}"),
    ("sum", r"\sum_{i=1}^{n} i"),
    ("integral", r"\int_0^1 x\,dx"),
    ("greek", r"\alpha+\beta+\gamma"),
    ("scripts", r"x_{1}+x_{2}^{2}"),
    ("matrix", r"\begin{pmatrix}1 & 2\\3 & 4\end{pmatrix}"),
]


def render_fixtures() -> list[Path]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        for name, latex in FORMULAS:
            tex = directory / f"{name}.tex"
            tex.write_text(
                "\\documentclass[border=8pt]{standalone}\n"
                "\\usepackage{amsmath}\n"
                "\\begin{document}\n"
                f"${latex}$\n"
                "\\end{document}\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["xelatex", "-interaction=nonstopmode", "-halt-on-error", str(tex)],
                cwd=directory,
                check=False,
                capture_output=True,
            )
            pdf = directory / f"{name}.pdf"
            if not pdf.exists():
                continue
            target = FIXTURES / f"{name}.png"
            subprocess.run(
                ["sips", "-s", "format", "png", str(pdf), "--out", str(target)],
                check=False,
                capture_output=True,
            )
    return sorted(FIXTURES.glob("*.png"))


def run_model(pngs: list[Path], venv_python: Path) -> list[dict]:
    script = r"""
import json, sys, time, pathlib, os, inspect
from munch import Munch
from pix2tex.cli import LatexOCR
from PIL import Image
pkg = pathlib.Path(inspect.getfile(LatexOCR)).parent
os.chdir(pkg)
args = Munch({'config': str(pkg/'model'/'settings'/'config.yaml'), 'checkpoint': str(pkg/'model'/'checkpoints'/'weights.pth'),
              'no_cuda': True, 'no_resize': False, 'temperature': 0.01})
model = LatexOCR(arguments=args)
for path in sys.argv[1:]:
    img = Image.open(path)
    if img.mode in ('RGBA', 'LA'):
        white = Image.new('RGBA', img.size, 'white')
        img = Image.alpha_composite(white, img.convert('RGBA')).convert('RGB')
    else:
        img = img.convert('RGB')
    t = time.perf_counter()
    latex = model(img)
    print(json.dumps({'image': os.path.basename(path), 'latex': str(latex),
                      'elapsed_ms': int((time.perf_counter()-t)*1000)}))
"""
    result = subprocess.run(
        [str(venv_python), "-c", script, *[str(p) for p in pngs]],
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    rows = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            rows.append(json.loads(line))
    return rows


def main() -> int:
    pngs = render_fixtures()
    print(f"fixtures rendered: {len(pngs)}")
    expected = {name: latex for name, latex in FORMULAS}
    rows: list[dict] = []
    venv = os.environ.get("ICSTEX_PIX2TEX_ENV")
    if venv and Path(venv).exists():
        python = Path(venv) / "bin" / "python"
        results = run_model(pngs, python)
        for item in results:
            name = item["image"][: -len(".png")]
            rows.append(
                {
                    "fixture": name,
                    "expected_latex": expected.get(name, ""),
                    "recognized_latex": item["latex"],
                    "elapsed_ms": item["elapsed_ms"],
                }
            )
        OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
        with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print("CSV ->", OUT_CSV)
        for row in rows:
            print(f"  {row['fixture']:18s} {row['elapsed_ms']:4d}ms  {row['recognized_latex']}")
    else:
        print("ICSTEX_PIX2TEX_ENV not set; fixtures rendered only (no inference).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
