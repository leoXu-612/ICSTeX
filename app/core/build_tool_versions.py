"""Bounded version labels from actual process stdout, not executable attestation.

Only the initial driver/engine banners are inspected. Later document output,
cached logs and the export-time environment cannot fill missing historical data.
Auxiliary programs, packages and fonts are deliberately not inferred here.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.latex_tools import LaTeXEngine


MAX_BANNER_CHARS = 64 * 1024
_VERSION = r"([0-9]+(?:[.-][0-9]+)*(?:[a-z][0-9]*)?)"
_DRIVER = re.compile(r"Latexmk: This is Latexmk, [^\r\n]{0,200} Version " + _VERSION + r"\.$")
_ENGINE = re.compile(r"This is (pdfTeX|XeTeX|LuaHBTeX|LuaTeX), Version " + _VERSION + r"(?= |$)")
_DISTRIBUTION = re.compile(r"\((TeX Live [0-9]{4}|MiKTeX [0-9]+(?:\.[0-9]+){1,3})\)")


@dataclass(frozen=True)
class ToolVersion:
    program: str
    version: str
    distribution: str | None = None


@dataclass(frozen=True)
class BuildToolVersions:
    driver: ToolVersion | None = None
    engine: ToolVersion | None = None
    truncated: bool = False


def _engine_version(line: str, selected: LaTeXEngine) -> ToolVersion | None:
    if len(line) > 1024:
        return None
    match = _ENGINE.match(line)
    expected = {LaTeXEngine.AUTO: {"pdfTeX"}, LaTeXEngine.PDFLATEX: {"pdfTeX"},
                LaTeXEngine.XELATEX: {"XeTeX"}, LaTeXEngine.LUALATEX: {"LuaTeX", "LuaHBTeX"}}
    if match is None or match[1] not in expected[selected] or len(match[2]) > 64:
        return None
    distribution = _DISTRIBUTION.search(line)
    return ToolVersion(match[1], match[2], distribution[1] if distribution else None)


def capture_tool_versions(stdout: str, engine: LaTeXEngine, *, via_latexmk: bool) -> BuildToolVersions:
    """Parse labels only; no filesystem, subprocess, environment or network access.

    Driver children are not tied to configured executable paths: latexmk resolves
    them itself. The report must distinguish these labels from binary identity.
    Wrappers/unrecognized startup output yield unknown, not a search of TeX body.
    """
    truncated = len(stdout) > MAX_BANNER_CHARS
    prefix = stdout[:MAX_BANNER_CHARS]
    if truncated:
        prefix = prefix.rpartition("\n")[0]  # Never accept a cut-off banner.
    lines = prefix.splitlines()
    if not via_latexmk:
        first = next((line for line in lines if line.strip()), "")
        return BuildToolVersions(engine=_engine_version(first, engine), truncated=truncated)

    driver = None
    # latexmk's own startup banner precedes its first child command. Do not
    # search document output for another driver or engine after the first one.
    for index, line in enumerate(lines[:32]):
        match = _DRIVER.fullmatch(line)
        if match and len(match[1]) <= 64:
            driver = ToolVersion("latexmk", match[1])
            break
        if line.startswith(("Running '", "This is ", "(./")):
            break
    if driver is None:
        return BuildToolVersions(truncated=truncated)
    command = "pdflatex" if engine is LaTeXEngine.AUTO else engine.value
    for offset in range(index + 1, len(lines)):
        line = lines[offset]
        if line.startswith("This is "):
            break  # No recognized command boundary before the engine/body.
        if not line.startswith("Running '"):
            continue
        if not line.startswith(f"Running '{command} "):
            break
        candidate = offset + 1
        while candidate < len(lines) and (not lines[candidate].strip() or lines[candidate] == "------------"):
            candidate += 1
        observed = _engine_version(lines[candidate], engine) if candidate < len(lines) else None
        return BuildToolVersions(driver, observed, truncated)
    return BuildToolVersions(driver, truncated=truncated)
