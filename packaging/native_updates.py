"""Prepare pinned native updater SDKs for explicitly configured builds.

No publishing, key generation, Developer ID signing, or notarization occurs.
macOS bundles remain ad-hoc development builds until separate release signing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.app_updates import (CONFIG_NAME, UpdateConfiguration,
                                   process_architecture, read_update_configuration)


# Matches the current Qt 6.11 macOS binaries; do not inherit the build host OS.
MACOS_MIN_SYSTEM_VERSION = "13.0"

SDK_RELEASES = {
    "darwin": {
        "version": "2.9.6",
        "url": "https://github.com/sparkle-project/Sparkle/releases/download/2.9.6/Sparkle-2.9.6.tar.xz",
        "sha256": "52bf9e88cdd972fc0c81501377a880e90d47031bd8ca5462488f843e2609e192",
    },
    "win32": {
        "version": "0.9.4",
        "url": "https://github.com/vslavik/winsparkle/releases/download/v0.9.4/WinSparkle-0.9.4.zip",
        "sha256": "6037df37fc263bd1650a1c4949681a9d40ffe991d01f35892a406cb5d103c976",
    },
}


def verify_sdk_archive(archive: Path, target_platform: str) -> None:
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != SDK_RELEASES[target_platform]["sha256"]:
        raise ValueError("Updater SDK archive does not match the pinned upstream release")


def sparkle_plist(config: UpdateConfiguration) -> dict:
    return {
        "CFBundleVersion": str(config.release_sequence),
        "LSMinimumSystemVersion": MACOS_MIN_SYSTEM_VERSION,
        "SUFeedURL": config.feed_url, "SUPublicEDKey": config.public_key,
        "SUEnableAutomaticChecks": False, "SUAutomaticallyUpdate": False,
        "SUAllowsAutomaticUpdates": False, "SUEnableSystemProfiling": False,
        "SUShowReleaseNotes": False, "SUEnableJavaScript": False,
        "SUVerifyUpdateBeforeExtraction": True, "SURequireSignedFeed": True,
        "SUSignedFeedFailureExpirationInterval": 0,
    }


def compile_sparkle_bridge(sdk: Path, output: Path, architecture: str) -> None:
    if sys.platform != "darwin":
        raise ValueError("The Sparkle bridge must be compiled on macOS")
    subprocess.run([
        "xcrun", "clang", "-fobjc-arc", "-dynamiclib", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-parameter", "-arch", architecture, "-F", str(sdk),
        f"-mmacosx-version-min={MACOS_MIN_SYSTEM_VERSION}",
        "-framework", "Foundation", "-framework", "Sparkle",
        "-Wl,-rpath,@loader_path", "-Wl,-install_name,@rpath/ICSTeXUpdateBridge.dylib",
        str(ROOT / "packaging" / "native_updates" / "sparkle_bridge.m"), "-o", str(output),
    ], check=True)


def prepare_runtime(archive: Path, config: UpdateConfiguration, output: Path) -> None:
    """Generate a new runtime directory, never overwrite an existing one."""
    verify_sdk_archive(archive, config.target_platform)
    if output.exists():
        raise ValueError("Choose a new runtime output directory; existing files are preserved")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".icstex-updater-", dir=output.parent) as temporary:
        stage = Path(temporary) / "runtime"
        stage.mkdir()
        licenses = stage / "licenses"
        licenses.mkdir()
        if config.target_platform == "darwin":
            sdk = Path(temporary) / "sdk"
            sdk.mkdir()
            with tarfile.open(archive, "r:xz") as bundle:
                bundle.extractall(sdk, filter="data")
            framework = sdk / "Sparkle.framework"
            with (framework / "Resources" / "Info.plist").open("rb") as stream:
                info = plistlib.load(stream)
            if info["CFBundleShortVersionString"] != SDK_RELEASES["darwin"]["version"]:
                raise ValueError("Unexpected Sparkle framework version")
            frameworks = stage / "Frameworks"
            frameworks.mkdir()
            shutil.copytree(framework, frameworks / framework.name, symlinks=True)
            compile_sparkle_bridge(sdk, frameworks / "ICSTeXUpdateBridge.dylib", config.architecture)
            shutil.copy2(sdk / "LICENSE", licenses / "Sparkle-LICENSE")
        else:
            directory = "ARM64" if config.architecture == "arm64" else "x64"
            prefix = f"WinSparkle-{SDK_RELEASES['win32']['version']}"
            updates = stage / "updates"
            updates.mkdir()
            with zipfile.ZipFile(archive) as bundle:
                (updates / "WinSparkle.dll").write_bytes(bundle.read(f"{prefix}/{directory}/Release/WinSparkle.dll"))
                for name in ("COPYING", "COPYING.expat"):
                    (licenses / f"WinSparkle-{name}").write_bytes(bundle.read(f"{prefix}/{name}"))
        (stage / CONFIG_NAME).write_text(json.dumps(config.as_dict(), indent=2) + "\n", encoding="utf-8")
        (stage / "sdk-receipt.json").write_text(
            json.dumps(SDK_RELEASES[config.target_platform], indent=2) + "\n", encoding="utf-8")
        stage.rename(output)


def runtime_from_environment() -> tuple[Path | None, UpdateConfiguration | None]:
    value = os.environ.get("ICSTEX_UPDATE_RUNTIME")
    if not value:
        return None, None
    runtime = Path(value).expanduser().resolve(strict=True)
    config = read_update_configuration(runtime / CONFIG_NAME)
    if (config.target_platform, config.architecture) != (sys.platform, process_architecture()):
        raise ValueError("Updater runtime must match the build Python platform and architecture")
    native = (runtime / "Frameworks" / "ICSTeXUpdateBridge.dylib" if sys.platform == "darwin"
              else runtime / "updates" / "WinSparkle.dll")
    if not native.is_file():
        raise ValueError("Updater runtime is incomplete")
    return runtime, config


def runtime_datas(runtime: Path | None) -> list[tuple[str, str]]:
    if runtime is None:
        return []
    return [(str(runtime / CONFIG_NAME), "app/assets"),
            (str(runtime / "licenses"), "app/assets/updater-licenses")]


def embed_macos_runtime(app_path: Path, runtime: Path) -> None:
    """Part of spec generation, before public signing/distribution."""
    frameworks = app_path / "Contents" / "Frameworks"
    frameworks.mkdir(exist_ok=True)
    target = frameworks / "Sparkle.framework"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(runtime / "Frameworks" / "Sparkle.framework", target, symlinks=True)
    shutil.copy2(runtime / "Frameworks" / "ICSTeXUpdateBridge.dylib", frameworks)
    # Re-establish local integrity after embedding. This is not Developer ID.
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app_path)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app_path)], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True, help="Pinned upstream SDK archive")
    parser.add_argument("--config", type=Path, required=True, help="Maintainer-provided public configuration")
    parser.add_argument("--output", type=Path, required=True, help="New runtime directory")
    args = parser.parse_args()
    config = read_update_configuration(args.config)
    prepare_runtime(args.archive.resolve(), config, args.output.resolve())
    print(f"Prepared native update runtime: {args.output}")
    print("Not a release. Signing, feed publication and installation acceptance remain required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
