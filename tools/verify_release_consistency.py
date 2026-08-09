#!/usr/bin/env python3
"""Validate that source, checked-in release metadata, and local assets agree."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import update_release_site


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "release" / "release-manifest.json"
SITE_PATH = ROOT / "website" / "release.json"
WEBSITE_PATH = ROOT / "website"


class ReleaseContractParser(HTMLParser):
    """Collect the release-facing HTML contract without executing JavaScript."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.bindings: dict[str, list[str]] = {}
        self.heading_levels: list[int] = []
        self.images: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if element_id := attributes.get("id"):
            self.ids.append(element_id)
        if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
            self.heading_levels.append(int(tag[1]))
        if tag == "img":
            self.images.append(attributes)
        for name in (
            "data-release",
            "data-release-link",
            "data-release-download",
            "data-release-sha",
            "data-release-document",
        ):
            if value := attributes.get(name):
                self.bindings.setdefault(name, []).append(value)


def validate_html_contracts(generated: dict[str, object], problems: list[str]) -> None:
    """Validate every static page against the generated release projection."""
    allowed_text = {"version", "tag", "channel", "name"}
    allowed_links = {"repository", "issues", "releases", "limitations", "architecture"}
    allowed_assets = {"macos-primary", "macos-dmg", "macos-zip", "windows-arm64"}
    documents = {str(item) for item in generated.get("documents", [])}
    html_files = sorted(WEBSITE_PATH.rglob("*.html"))
    if not html_files:
        fail(problems, "website has no HTML pages")
        return

    for path in html_files:
        parser = ReleaseContractParser()
        try:
            parser.feed(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            fail(problems, f"cannot read {path.relative_to(ROOT)}: {exc}")
            continue
        relative = path.relative_to(ROOT)
        if len(parser.ids) != len(set(parser.ids)):
            fail(problems, f"duplicate HTML id in {relative}")
        if parser.heading_levels.count(1) != 1:
            fail(problems, f"{relative} must contain exactly one h1")
        for previous, current in zip(parser.heading_levels, parser.heading_levels[1:]):
            if current - previous > 1:
                fail(problems, f"heading level skips in {relative}")
        for image in parser.images:
            if "alt" not in image:
                fail(problems, f"image without alt in {relative}")
            if not image.get("width") or not image.get("height"):
                fail(problems, f"image without dimensions in {relative}")

        for value in parser.bindings.get("data-release", []):
            if value not in allowed_text:
                fail(problems, f"unknown data-release binding {value!r} in {relative}")
        for value in parser.bindings.get("data-release-link", []):
            if value not in allowed_links:
                fail(problems, f"unknown data-release-link binding {value!r} in {relative}")
        for attribute in ("data-release-download", "data-release-sha"):
            for value in parser.bindings.get(attribute, []):
                if value not in allowed_assets:
                    fail(problems, f"unknown {attribute} binding {value!r} in {relative}")
        for value in parser.bindings.get("data-release-document", []):
            if value not in documents:
                fail(problems, f"unknown release document {value!r} in {relative}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fail(problems: list[str], message: str) -> None:
    problems.append(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-tag-at-head", action="store_true")
    args = parser.parse_args()

    problems: list[str] = []
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        generated = update_release_site.generated_release_data(manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Release consistency FAILED: {exc}", file=sys.stderr)
        return 1

    try:
        site = json.loads(SITE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Release consistency FAILED: {exc}", file=sys.stderr)
        return 1

    for key in (
        "repository",
        "version",
        "tag",
        "channel",
        "release_name",
        "github_repository_public",
        "github_release_published",
    ):
        if site.get(key) != generated.get(key):
            fail(problems, f"website/release.json {key} disagrees with generated release data")
    if site != generated:
        fail(problems, "website/release.json must be generated by tools/update_release_site.py")

    validate_html_contracts(generated, problems)
    for path in sorted(WEBSITE_PATH.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for value in (str(generated["version"]), str(generated["tag"])):
            if value in text:
                fail(problems, f"hard-coded release constant {value!r} in {path.relative_to(ROOT)}")
    for path in sorted(WEBSITE_PATH.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        for value in (str(generated["version"]), str(generated["tag"])):
            if value in text:
                fail(problems, f"hard-coded release constant {value!r} in {path.relative_to(ROOT)}")

    for document in manifest.get("documents", []):
        path = ROOT / "release" / str(document)
        if not path.is_file():
            fail(problems, f"missing release document: {path.relative_to(ROOT)}")

    for entry in manifest.get("assets", []):
        if not isinstance(entry, dict):
            fail(problems, "manifest has a non-object asset")
            continue
        path = ROOT / "release" / str(entry.get("name", ""))
        if not path.is_file():
            fail(problems, f"missing release asset: {path.relative_to(ROOT)}")
            continue
        expected = entry.get("sha256")
        actual = sha256(path)
        if expected != actual:
            fail(problems, f"sha256 mismatch: {path.name}")

    version = generated["version"]
    for document in ("INSTALLATION.md", "KNOWN_LIMITATIONS.md", "RELEASE_NOTES.md"):
        text = (ROOT / "release" / document).read_text(encoding="utf-8")
        if str(version) not in text:
            fail(problems, f"{document} does not mention version {version}")

    if args.require_tag_at_head:
        tag = str(generated["tag"])
        try:
            tag_commit = subprocess.check_output(["git", "rev-parse", f"{tag}^{{commit}}"], cwd=ROOT, text=True).strip()
            head_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        except subprocess.CalledProcessError as exc:
            fail(problems, f"cannot resolve release tag: {exc}")
        else:
            if tag_commit != head_commit:
                fail(problems, f"{tag} must resolve to HEAD before release")

    if problems:
        print("Release consistency FAILED:", file=sys.stderr)
        print("\n".join(f"- {problem}" for problem in problems), file=sys.stderr)
        return 1
    print(f"Release consistency PASS: {generated['tag']} ({generated['repository']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
