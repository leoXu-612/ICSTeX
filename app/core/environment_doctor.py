from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from platform import platform, python_version
from shutil import which
import subprocess
from typing import Iterable, Sequence

from app import __app_name__, __version__
from app.core.diagnostics import Diagnostic
from app.core.latex_tools import LaTeXToolchain, detect_toolchain


LATEX_TOOLS: tuple[str, ...] = (
    "latexmk",
    "pdflatex",
    "xelatex",
    "lualatex",
    "biber",
    "bibtex",
    "texcount",
    "synctex",
)


@dataclass(frozen=True)
class ToolStatus:
    name: str
    path: str | None
    version: str | None = None
    required: bool = False

    @property
    def is_available(self) -> bool:
        return self.path is not None

    @property
    def status_label(self) -> str:
        return "可用" if self.is_available else "缺失"


@dataclass(frozen=True)
class EnvironmentReport:
    app_name: str
    app_version: str
    system: str
    python: str
    tools: tuple[ToolStatus, ...]
    recommendations: tuple[str, ...]

    @property
    def compile_ready(self) -> bool:
        return any(tool.name in {"latexmk", "pdflatex", "xelatex", "lualatex"} and tool.is_available for tool in self.tools)

    def as_text(self) -> str:
        lines = [
            f"{self.app_name} 环境诊断报告",
            f"App 版本：{self.app_version}",
            f"系统：{self.system}",
            f"Python：{self.python}",
            "",
            "LaTeX 工具：",
        ]
        for tool in self.tools:
            marker = "✓" if tool.is_available else "✗"
            required = "（编译核心）" if tool.required else ""
            path = tool.path or "未找到"
            version = f" | {tool.version}" if tool.version else ""
            lines.append(f"{marker} {tool.name}{required}: {path}{version}")

        lines.append("")
        lines.append("建议：")
        lines.extend(f"- {item}" for item in self.recommendations)
        return "\n".join(lines)


@dataclass(frozen=True)
class FeedbackMetadata:
    selected_engine: str | None = None
    root_file: Path | str | None = None
    root_source: str | None = None
    latest_compile_seconds: float | None = None
    word_count_mode: str | None = None


def build_environment_report(toolchain: LaTeXToolchain | None = None) -> EnvironmentReport:
    toolchain = toolchain or detect_toolchain()
    tools = tuple(_tool_status(name, _tool_path(toolchain, name), required=name in {"latexmk", "pdflatex"}) for name in LATEX_TOOLS)
    return EnvironmentReport(
        app_name=__app_name__,
        app_version=__version__,
        system=platform(),
        python=python_version(),
        tools=tools,
        recommendations=_recommendations(tools),
    )


def _tool_path(toolchain: LaTeXToolchain, name: str) -> str | None:
    value = getattr(toolchain, name, None)
    if isinstance(value, str) and value:
        return value
    return which(name)


def _tool_status(name: str, path: str | None, *, required: bool = False) -> ToolStatus:
    return ToolStatus(name=name, path=path, version=_tool_version(path) if path else None, required=required)


def _tool_version(path: str) -> str | None:
    commands: Iterable[list[str]] = ([path, "--version"], [path, "-version"])
    for command in commands:
        try:
            process = subprocess.run(command, capture_output=True, text=True, timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            continue
        output = (process.stdout or process.stderr).strip()
        if output:
            return output.splitlines()[0].strip()
    return None


FEEDBACK_LOG_TAIL_LINES = 80
FEEDBACK_LOG_MAX_CHARS = 4000


def build_feedback_bundle(
    report: EnvironmentReport,
    *,
    recent_log: str | None = None,
    diagnostics: Sequence[Diagnostic] | None = None,
    project_file: Path | str | None = None,
    metadata: FeedbackMetadata | None = None,
) -> str:
    """Compose a privacy-friendly diagnostic bundle for sharing with maintainers.

    The bundle never includes the user's `.tex` content. Project paths are
    redacted to the file name. The recent compile log is truncated to the
    tail to keep the bundle small enough for chat/email sharing.
    """
    lines: list[str] = [f"{report.app_name} 反馈包"]
    lines.append("（不含论文正文，仅供排错使用；如需发给同学/老师，请先自行确认内容。）")
    lines.append("")
    lines.append(report.as_text())

    project_label = _project_label(project_file)
    metadata_lines = _format_metadata_lines(metadata)
    if project_label is not None or metadata_lines:
        lines.append("")
        lines.append("当前项目：")
        if project_label is not None:
            lines.append(f"- 文件名：{project_label}")
        lines.extend(metadata_lines)

    diagnostic_lines = _format_diagnostic_lines(diagnostics)
    if diagnostic_lines:
        lines.append("")
        lines.append("项目检查摘要：")
        lines.extend(diagnostic_lines)

    log_tail = _format_log_tail(recent_log)
    if log_tail:
        lines.append("")
        lines.append(f"最近编译日志（末尾 {FEEDBACK_LOG_TAIL_LINES} 行，最长 {FEEDBACK_LOG_MAX_CHARS} 字符）：")
        lines.append(log_tail)

    # Project/root file fields are already reduced to basenames above, but the
    # env report's tool paths and the raw compile-log tail can still embed
    # absolute paths (username + project directory name). Scrub those so the
    # bundle does not leak the home directory or the project folder name.
    # ponytail: substring replace, not a path parser; covers the common case.
    return _redact_sensitive("\n".join(lines), project_file)


def _redact_sensitive(text: str, project_file: Path | str | None) -> str:
    if project_file is not None:
        project_dir = str(Path(project_file).parent)
        if project_dir not in ("", "."):
            text = text.replace(project_dir, "<project>")
    home = str(Path.home())
    if home:
        text = text.replace(home, "~")
    return text


def _project_label(project_file: Path | str | None) -> str | None:
    if project_file is None:
        return None
    name = Path(project_file).name
    return name or None


def _format_metadata_lines(metadata: FeedbackMetadata | None) -> list[str]:
    if metadata is None:
        return []
    lines: list[str] = []
    root_file = _project_label(metadata.root_file)
    if root_file:
        lines.append(f"- Root 文件：{root_file}")
    if metadata.root_source:
        lines.append(f"- Root 来源：{metadata.root_source}")
    if metadata.selected_engine:
        lines.append(f"- 当前引擎：{metadata.selected_engine}")
    if metadata.latest_compile_seconds is not None:
        lines.append(f"- 最近编译耗时：{metadata.latest_compile_seconds:.2f}s")
    if metadata.word_count_mode:
        lines.append(f"- 字数统计模式：{metadata.word_count_mode}")
    return lines


def _format_diagnostic_lines(diagnostics: Sequence[Diagnostic] | None) -> list[str]:
    if not diagnostics:
        return []
    lines: list[str] = []
    for diagnostic in diagnostics:
        location = ""
        if diagnostic.file is not None or diagnostic.line is not None:
            file_name = Path(diagnostic.file).name if diagnostic.file is not None else "?"
            line_label = str(diagnostic.line) if diagnostic.line is not None else "?"
            location = f"（{file_name}:{line_label}）"
        lines.append(f"- [{diagnostic.severity_label}] {diagnostic.title}{location}")
    return lines


def _format_log_tail(recent_log: str | None) -> str:
    if not recent_log:
        return ""
    tail = "\n".join(recent_log.splitlines()[-FEEDBACK_LOG_TAIL_LINES:])
    if len(tail) > FEEDBACK_LOG_MAX_CHARS:
        tail = "… " + tail[-FEEDBACK_LOG_MAX_CHARS:]
    return tail


def _recommendations(tools: tuple[ToolStatus, ...]) -> tuple[str, ...]:
    available = {tool.name for tool in tools if tool.is_available}
    recommendations: list[str] = []
    if not available.intersection({"latexmk", "pdflatex", "xelatex", "lualatex"}):
        recommendations.append("未找到 LaTeX 编译器。macOS 建议安装完整 MacTeX；Windows 建议安装 MiKTeX 或 TeX Live。")
    elif "latexmk" not in available:
        recommendations.append("未找到 latexmk。ICSTeX 可以直接调用引擎编译，但 latexmk 更适合自动处理多轮编译、引用和目录。")
    else:
        recommendations.append("编译核心可用。若某个项目仍失败，请查看“错误/检查”面板里的具体 LaTeX 信息。")

    if "texcount" not in available:
        recommendations.append("未找到 texcount，字数统计会自动降级为 Python 简化统计，结果可能与 Overleaf 不完全一致。")
    if "biber" not in available and "bibtex" not in available:
        recommendations.append("未找到 biber 或 bibtex，复杂参考文献项目可能无法完整编译。")
    if "synctex" not in available:
        recommendations.append("未找到 synctex，PDF 与源码双向定位可能不可用。")
    return tuple(recommendations)
