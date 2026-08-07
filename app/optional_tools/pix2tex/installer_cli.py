"""CLI entry run by the GUI manager via QProcess (non-blocking install)."""
from __future__ import annotations

import argparse
import json
import sys

from app.optional_tools.pix2tex import installer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    install_parser = sub.add_parser("install")
    install_parser.add_argument("--python", default=None)
    install_parser.add_argument("--with-models", action="store_true")
    sub.add_parser("remove")
    args = parser.parse_args(argv)
    if args.command == "status":
        print(json.dumps(installer.status(), ensure_ascii=False))
    elif args.command == "install":
        result = installer.install(args.python)
        if args.with_models:
            result = {**result, "models": installer.download_models()}
        print(json.dumps(result, ensure_ascii=False))
    elif args.command == "remove":
        installer.remove()
        print(json.dumps(installer.status(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
