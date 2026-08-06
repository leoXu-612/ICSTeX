from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
import subprocess

from app.core.latex_tools import LaTeXToolchain, detect_toolchain
from app.core.process_env import latex_subprocess_env


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncPosition:
    file: Path
    line: int
    column: int | None = None
    page: int | None = None
    x: float | None = None
    y: float | None = None


def source_to_pdf(
    tex_file: str | Path,
    line: int,
    pdf_file: str | Path,
    toolchain: LaTeXToolchain | None = None,
) -> SyncPosition | None:
    tools = toolchain or detect_toolchain()
    if not tools.synctex:
        return None
    output = _run_synctex(
        tools, ["view", "-i", f"{line}:1:{tex_file}", "-o", str(pdf_file)]
    )
    if output is None:
        return None
    return _parse_synctex_output(output, fallback_file=Path(tex_file), fallback_line=line)


def pdf_to_source(
    pdf_file: str | Path,
    page: int,
    x: float,
    y: float,
    toolchain: LaTeXToolchain | None = None,
) -> SyncPosition | None:
    tools = toolchain or detect_toolchain()
    if not tools.synctex:
        return None
    output = _run_synctex(tools, ["edit", "-o", f"{page}:{x}:{y}:{pdf_file}"])
    if output is None:
        return None
    return _parse_synctex_output(output)


def _run_synctex(tools: LaTeXToolchain, args: list[str]) -> str | None:
    try:
        process = subprocess.run(
            [tools.synctex, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=latex_subprocess_env(),
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("synctex invocation failed: %s", exc)
        return None
    return process.stdout


def _parse_synctex_output(
    output: str,
    fallback_file: Path | None = None,
    fallback_line: int | None = None,
) -> SyncPosition | None:
    values: dict[str, str] = {}
    for line in output.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip().lower()] = value.strip()

    file_value = values.get("input") or values.get("file")
    line_value = values.get("line")
    page_value = values.get("page")
    x_value = values.get("x")
    y_value = values.get("y")

    if not file_value and not fallback_file:
        return None
    if not line_value and fallback_line is None:
        return None

    try:
        line_number = int(line_value) if line_value else int(fallback_line or 1)
    except ValueError:
        line_number = int(fallback_line or 1)

    return SyncPosition(
        file=Path(file_value).expanduser().resolve() if file_value else fallback_file.resolve(),
        line=line_number,
        page=_int_or_none(page_value),
        x=_float_or_none(x_value),
        y=_float_or_none(y_value),
    )


def _int_or_none(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"-?\d+", value)
    return int(match.group(0)) if match else None


def _float_or_none(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    return float(match.group(0)) if match else None
