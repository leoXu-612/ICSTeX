#!/usr/bin/env python3
"""Generate the checked-in release metadata consumed by the static website."""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
APP_INIT = ROOT / "app" / "__init__.py"
MANIFEST_PATH = ROOT / "release" / "release-manifest.json"
OUTPUT_PATH = ROOT / "website" / "release.json"
REPOSITORY = "leoXu-612/ICSTeX"


def read_app_version() -> str:
    tree = ast.parse(APP_INIT.read_text(encoding="utf-8"), filename=str(APP_INIT))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise ValueError("app/__init__.py does not define a literal __version__")


def generated_release_data(manifest: dict[str, object]) -> dict[str, object]:
    version = read_app_version()
    if manifest.get("version") != version:
        raise ValueError(f"manifest version {manifest.get('version')!r} does not match app version {version!r}")
    tag = manifest.get("tag")
    if tag != f"v{version}":
        raise ValueError(f"manifest tag {tag!r} must be v{version}")

    assets: list[dict[str, object]] = []
    for entry in manifest.get("assets", []):
        if not isinstance(entry, dict):
            raise ValueError("manifest assets must be objects")
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("every manifest asset needs a name")
        assets.append(
            {
                **entry,
                "download_url": f"https://github.com/{REPOSITORY}/releases/download/{tag}/{quote(name)}",
            }
        )

    return {
        "schema_version": 1,
        "repository": REPOSITORY,
        "version": version,
        "tag": tag,
        "channel": manifest["channel"],
        "release_name": manifest["release_name"],
        "github_release_published": manifest["github_release_published"],
        "release_page_url": f"https://github.com/{REPOSITORY}/releases/tag/{tag}",
        "releases_url": f"https://github.com/{REPOSITORY}/releases",
        "assets": assets,
        "documents": manifest["documents"],
        "limitations": manifest["limitations"],
    }


def render(data: dict[str, object]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if website/release.json is stale")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    output = render(generated_release_data(manifest))
    if args.check:
        actual = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
        if actual != output:
            print(f"stale generated file: {OUTPUT_PATH.relative_to(ROOT)}", file=sys.stderr)
            return 1
        print(f"release site metadata is current: {OUTPUT_PATH.relative_to(ROOT)}")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(f"generated {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
