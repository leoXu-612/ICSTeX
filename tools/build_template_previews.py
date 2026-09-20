"""Precompile built-in template examples; never called by the application UI."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.compiler import CompileManager
from app.core.latex_insertions import TEMPLATES
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.core.magic_comments import parse_magic_comments
from app.core.text_encoding import write_latex_text_atomic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True, help="New directory for compiler evidence")
    parser.add_argument("--output", type=Path, default=ROOT / "app/assets/template-previews")
    args = parser.parse_args()
    renderer = shutil.which("pdftoppm")
    if renderer is None:
        raise SystemExit("pdftoppm is required to regenerate previews; the app does not need it")
    args.workdir.mkdir(parents=True, exist_ok=False)
    args.output.mkdir(parents=True, exist_ok=True)
    tools = detect_toolchain()
    hashes = {}
    for key, template in TEMPLATES.items():
        folder = args.workdir / key
        folder.mkdir()
        source = folder / "main.tex"
        write_latex_text_atomic(source, template.text, encoding="utf-8")
        engine = parse_magic_comments(template.text).program or LaTeXEngine.PDFLATEX
        manager = CompileManager(source, toolchain=tools, engine=engine)
        result = manager.compile_now(timeout_seconds=60)
        if result is None or not result.ok:
            raise RuntimeError(f"Template {key} failed; inspect {folder}")
        subprocess.run([renderer, "-f", "1", "-singlefile", "-scale-to", "800", "-png",
                        str(result.pdf_file), str(args.output / key)], check=True, timeout=30)
        hashes[key] = hashlib.sha256(template.text.encode("utf-8")).hexdigest()
        print(f"{key}: compiled and rendered", flush=True)
    (args.output / "manifest.json").write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
