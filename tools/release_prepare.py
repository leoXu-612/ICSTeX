#!/usr/bin/env python3
"""Run the offline-only preparation steps for an ICSTeX release candidate."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import update_release_site


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="only verify generated metadata; do not write")
    args = parser.parse_args()

    generator = [sys.executable, str(ROOT / "tools" / "update_release_site.py")]
    if args.check:
        generator.append("--check")
    subprocess.run(generator, cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "tools" / "verify_release_consistency.py")], cwd=ROOT, check=True)
    print("Offline release preparation PASS. No tag, push, GitHub Release, or site deployment was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
