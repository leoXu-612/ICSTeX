#!/usr/bin/env bash
set -euo pipefail

# Local simulation of .github/workflows/modular-layout.yml commands.
# Run this before pushing so the GitHub jobs are unlikely to fail on
# command-level errors. Requires Python 3.12 + requirements.txt + xelatex
# (the macOS job needs TeX; the ubuntu job subset does not).

cd "$(dirname "$0")/.."
export QT_QPA_PLATFORM=offscreen

echo "== ubuntu job: compile check =="
python3 -m compileall -q app tests packaging/install_build_dependencies.py

echo "== ubuntu job: schema / core / golden unit subset =="
python3 -m unittest \
  tests.test_blocks \
  tests.test_block_migration \
  tests.test_layout \
  tests.test_table_model \
  tests.test_table_strategy \
  tests.test_source_merge \
  tests.test_source_registry \
  tests.test_export_package \
  tests.test_determinism \
  tests.test_formula_adapter \
  tests.test_project_io

echo "== macOS job: full suite =="
python3 -m unittest discover -s tests

echo "== macOS job: build demo =="
python3 -c "from app.core.blocks.demo import build_demo; from pathlib import Path; build_demo(Path('demo'))"

echo "CI simulation OK"
