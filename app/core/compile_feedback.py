"""Single mapping from CompileOutcome to user-facing Chinese presentation.

Status bar, log, and PDF-state code must all read from here instead of
duplicating strings. Headlines use the root filename, never absolute paths;
raw commands/output stay in the detailed log.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.compiler import CompileOutcome, CompileResult
from app.core.diagnostics import explain_latex_error


@dataclass(frozen=True)
class OutcomePresentation:
    title: str
    detail: str
    severity: str  # "success" | "warning" | "error"
    next_action: str


_PRESENTATIONS: dict[CompileOutcome, OutcomePresentation] = {
    CompileOutcome.SUCCESS: OutcomePresentation(
        "编译成功", "PDF 已更新。", "success", "可以继续写作，或导出 PDF。"
    ),
    CompileOutcome.STOPPED: OutcomePresentation(
        "编译已停止",
        "本次编译被手动停止。",
        "warning",
        "需要时可重新编译；当前显示的 PDF 是较早的成功版本。",
    ),
    CompileOutcome.TIMEOUT: OutcomePresentation(
        "编译超时",
        "编译超过时限，已终止进程；当前显示的 PDF 是较早的成功版本。",
        "error",
        "请检查是否有挂起的编译任务，或减少单次编译内容后重试。",
    ),
    CompileOutcome.TOOLCHAIN_MISSING: OutcomePresentation(
        "未找到可用的 LaTeX 编译器",
        "所需的编译引擎不在 PATH 中。",
        "error",
        "请安装 MacTeX / TeX Live / MiKTeX，或打开“环境检查”查看详情。",
    ),
    CompileOutcome.ROOT_FILE_MISSING: OutcomePresentation(
        "根 LaTeX 文件不存在",
        "要编译的根文件已被移动或删除。",
        "error",
        "请确认文件位置，或重新保存文档。",
    ),
    CompileOutcome.PROCESS_START_FAILED: OutcomePresentation(
        "无法启动编译进程",
        "操作系统拒绝启动编译命令。",
        "error",
        "请查看日志中的系统错误信息，或运行“环境检查”。",
    ),
    CompileOutcome.LATEX_ERROR: OutcomePresentation(
        "编译失败",
        "LaTeX 源码存在错误。",
        "error",
        "请查看“错误”面板中的第一条提示并修正后重新编译。",
    ),
    CompileOutcome.OUTPUT_MISSING: OutcomePresentation(
        "编译结束，但没有生成有效 PDF",
        "编译进程正常退出，但未产生非空 PDF。",
        "error",
        "请尝试“清理缓存后重新编译”。",
    ),
    CompileOutcome.INTERNAL_ERROR: OutcomePresentation(
        "ICSTeX 处理编译结果时发生错误",
        "这是 ICSTeX 内部问题，不是论文源码错误。",
        "error",
        "请通过“复制反馈包”把诊断信息反馈给我们。",
    ),
}


def presentation_for(outcome: CompileOutcome) -> OutcomePresentation:
    return _PRESENTATIONS[outcome]


def headline_for(result: CompileResult, *, engine_name: str | None = None) -> str:
    """Beginner-facing one-line summary for the status bar / log."""
    presentation = presentation_for(result.outcome)
    root_name = result.root_file.name
    if result.outcome is CompileOutcome.SUCCESS:
        engine_part = f"{engine_name}，" if engine_name else ""
        return f"{presentation.title}：{root_name}（{engine_part}{result.duration_seconds:.2f}s）"
    if result.outcome is CompileOutcome.LATEX_ERROR and result.errors:
        # The first actionable diagnostic leads; generic latexmk footer text
        # must never be the headline.
        diagnostic = explain_latex_error(result.errors[0], root_file=result.root_file)
        return f"{presentation.title}：{diagnostic.title}：{diagnostic.message}"
    if result.outcome is CompileOutcome.PROCESS_START_FAILED and result.stderr:
        first_line = result.stderr.strip().splitlines()[0]
        return f"{presentation.title}：{first_line}"
    return f"{presentation.title}（{root_name}）"
