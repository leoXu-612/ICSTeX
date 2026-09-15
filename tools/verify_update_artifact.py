"""Read-only updater bundle/source and signed feed checks; emit one receipt."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import marshal
from pathlib import Path
import plistlib
import re
import subprocess
import xml.etree.ElementTree as ET

from PyInstaller.archive.readers import CArchiveReader


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--feed", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    source, bundle = args.source.resolve(), args.bundle.resolve()
    executable = bundle / "Contents/MacOS/ICSTeX"
    container = CArchiveReader(str(executable))
    pyz = container.open_embedded_archive("PYZ.pyz")
    baseline = CArchiveReader(str(args.baseline / "Contents/MacOS/ICSTeX")).open_embedded_archive("PYZ.pyz")
    modules = {key for key in pyz.toc if key == "app" or key.startswith("app.")}
    old_modules = {key for key in baseline.toc if key == "app" or key.startswith("app.")}
    problems, missing, matches = [], [], []
    source_hash = hashlib.sha256()
    for path in sorted((source / "app").rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.name == ".DS_Store":
            continue
        source_hash.update(path.relative_to(source / "app").as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
        if path.suffix != ".py":
            continue
        module = ".".join(path.relative_to(source).with_suffix("").parts).removesuffix(".__init__")
        if module == "app.__main__":
            actual = marshal.loads(container.extract("__main__"))
        elif module in modules:
            actual = pyz.extract(module)
        else:
            missing.append(module)
            continue
        if actual != compile(path.read_bytes(), str(path), "exec", optimize=0, dont_inherit=True):
            problems.append(f"source mismatch: {module}")
        else:
            matches.append(module)
    for name in old_modules - modules:
        problems.append(f"lost previously bundled module: {name}")
    for path in (source / "app/assets").rglob("*"):
        if path.is_file() and path.name != ".DS_Store":
            target = bundle / "Contents/Resources/app/assets" / path.relative_to(source / "app/assets")
            if not target.is_file() or digest(path) != digest(target):
                problems.append(f"asset mismatch: {path.name}")
    if "runtime_hook_update_guard" not in container.toc or "app.core.update_install_guard" not in modules:
        problems.append("missing startup installation guard")
    helper = bundle / "Contents/Helpers/ICSTeXInstallGuard"
    if not helper.is_file():
        problems.append("missing native installation guard")
    info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
    config = json.loads((bundle / "Contents/Resources/app/assets/app-update.json").read_text())
    expected = {"CFBundleShortVersionString": config["version"], "CFBundleVersion": str(config["release_sequence"]),
                "SUFeedURL": config["feed_url"], "SUPublicEDKey": config["public_key"],
                "SURequireSignedFeed": True, "SUVerifyUpdateBeforeExtraction": True,
                "SUSignedFeedFailureExpirationInterval": 0, "SUAllowsAutomaticUpdates": False}
    for key, value in expected.items():
        if info.get(key) != value:
            problems.append(f"configuration mismatch: {key}")
    signature = subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(bundle)], capture_output=True, text=True)
    if signature.returncode:
        problems.append("bundle signature integrity")
    report = {"bundle": str(bundle), "source": str(source), "app_source_sha256": source_hash.hexdigest(),
              "executable_sha256": digest(executable), "version": config["version"],
              "sequence": config["release_sequence"], "feed_url": config["feed_url"],
              "matched_modules_and_entry": len(matches), "not_packaged": missing,
              "newly_packaged": sorted(modules - old_modules), "signature_exit": signature.returncode,
              "architecture": subprocess.check_output(["lipo", "-archs", str(executable)], text=True).strip()}
    if args.feed:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(config["public_key"]))
        data = args.feed.read_bytes()
        match = re.search(rb"<!-- sparkle-signatures:\s*edSignature: ([A-Za-z0-9+/=]+)\s*length: (\d+)\s*-->\s*$", data)
        if not match or int(match[2]) != match.start():
            raise ValueError("Invalid signed feed envelope")
        public.verify(base64.b64decode(match[1]), data[:match.start()])
        ns = "{http://www.andymatuschak.org/xml-namespaces/sparkle}"
        items = ET.fromstring(data).findall("./channel/item")
        item = next(item for item in items if item.findtext(ns + "version") == str(config["release_sequence"]))
        if item.findtext(ns + "shortVersionString") != config["version"]:
            raise ValueError("Feed display version differs from bundle")
        if args.archive is None:
            raise ValueError("Archive required with feed")
        archive = args.archive.read_bytes()
        enclosure = item.find("enclosure")
        if int(enclosure.attrib["length"]) != len(archive):
            raise ValueError("Archive length mismatch")
        public.verify(base64.b64decode(enclosure.attrib[ns + "edSignature"]), archive)
        report.update(feed_sha256=digest(args.feed), archive_sha256=digest(args.archive),
                      archive_bytes=len(archive), signed_feed_and_archive_verified=True,
                      download_url=enclosure.attrib["url"])
    report.update(problems=problems, passed=not problems)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps(report, indent=2))
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
