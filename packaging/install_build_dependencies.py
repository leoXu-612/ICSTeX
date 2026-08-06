"""Install build dependencies with a small amount of cross-platform recovery.

The helper never changes system proxy settings. It only removes unreachable
loopback proxies from the environment passed to this pip subprocess, and it
prefers a local pylatexenc wheel when one was placed beside the source tree.
"""
from __future__ import annotations

import os
from pathlib import Path
import socket
import subprocess
import sys
from collections.abc import Callable, Mapping
from urllib.parse import urlparse


PROXY_VARIABLES = {
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "pip_proxy",
}
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
Probe = Callable[[str, int], bool]


def proxy_endpoint(value: str) -> tuple[str, int] | None:
    candidate = value.strip()
    if not candidate:
        return None
    parsed = urlparse(candidate if "://" in candidate else f"http://{candidate}")
    host = (parsed.hostname or "").lower()
    if host not in LOOPBACK_HOSTS:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return host, port


def endpoint_is_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def sanitized_proxy_environment(
    environment: Mapping[str, str],
    *,
    probe: Probe = endpoint_is_reachable,
) -> tuple[dict[str, str], tuple[str, ...]]:
    cleaned = dict(environment)
    removed: list[str] = []
    endpoint_cache: dict[tuple[str, int], bool] = {}
    for name, value in tuple(cleaned.items()):
        if name.casefold() not in PROXY_VARIABLES:
            continue
        endpoint = proxy_endpoint(value)
        if endpoint is None:
            continue
        if endpoint not in endpoint_cache:
            endpoint_cache[endpoint] = probe(*endpoint)
        reachable = endpoint_cache[endpoint]
        if reachable:
            continue
        cleaned.pop(name, None)
        removed.append(name)
    return cleaned, tuple(removed)


def find_local_pylatexenc_wheel(root: Path) -> Path | None:
    candidates = [
        *root.glob("pylatexenc-*.whl"),
        *(root / "packaging" / "wheels").glob("pylatexenc-*.whl"),
    ]
    files = sorted(path for path in candidates if path.is_file())
    return files[-1] if files else None


def install_commands(root: Path, python: str) -> tuple[tuple[str, ...], ...]:
    commands: list[tuple[str, ...]] = []
    wheel = find_local_pylatexenc_wheel(root)
    if wheel is not None:
        commands.append((python, "-m", "pip", "install", "--no-deps", str(wheel)))
    commands.append(
        (
            python,
            "-m",
            "pip",
            "install",
            "-r",
            str(root / "requirements.txt"),
            "-r",
            str(root / "requirements-packaging.txt"),
        )
    )
    return tuple(commands)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    environment, removed = sanitized_proxy_environment(os.environ)
    if removed:
        labels = ", ".join(sorted(removed, key=str.casefold))
        print(f"Ignoring unreachable local proxy variables for this build: {labels}", flush=True)
        print("System proxy settings were not changed.", flush=True)

    wheel = find_local_pylatexenc_wheel(root)
    if wheel is not None:
        print(f"Using local pylatexenc wheel: {wheel.name}", flush=True)

    for command in install_commands(root, sys.executable):
        result = subprocess.run(command, cwd=root, env=environment, check=False)
        if result.returncode:
            print("", file=sys.stderr)
            print("Dependency installation failed.", file=sys.stderr)
            print(
                "Check internet access, proxy settings, or place "
                "pylatexenc-2.10-py3-none-any.whl in the project root.",
                file=sys.stderr,
            )
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
