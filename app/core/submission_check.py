"""Read-only submission evidence, composed from existing project/build rules.

No saving, compilation, network or project mutation. A report is an observation
of identified inputs, never academic certification or export authorization.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from enum import Enum
import hashlib
import os
from pathlib import Path
from threading import Event
from time import time

from app.core.diagnostics import reference_diagnostics, package_diagnostics
from app.core.build_evidence import FinalBuildEvidence
from app.core.compiler import BuildPurpose, CompileOutcome
from app.core.latex_tools import LaTeXEngine, LaTeXToolchain
from app.core.block_submission import BlockCheckInput, block_inputs_unchanged, inspect_block_inputs
from app.core.paths import strip_latex_comments
from app.core.pdf_state import PdfBuildRecord, PdfFreshness
from app.core.project_profile import load_profile
from app.core.project_dependencies import (InputObservation, observe_input, read_project_source,
                                         safe_project_input, static_dependencies, SOURCE_SUFFIXES)
from app.core.word_count import WordCountResult, count_project_snapshot


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    CHECKING = "checking"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


STATUS_LABELS = {CheckStatus.PASS: "通过", CheckStatus.FAIL: "未通过",
                 CheckStatus.CHECKING: "检查中", CheckStatus.UNKNOWN: "未知",
                 CheckStatus.NOT_APPLICABLE: "不适用"}


@dataclass(frozen=True)
class BufferInput:
    path: Path | None
    text: str
    revision: int
    modified: bool = False


@dataclass(frozen=True)
class CheckRequest:
    key: tuple
    scope: Path | None
    root: Path | None
    buffers: tuple[BufferInput, ...]
    tools: LaTeXToolchain
    engine: LaTeXEngine
    final: PdfBuildRecord | None = None
    extra_inputs: tuple[Path, ...] = ()
    word_target: tuple[int | None, int | None] | None = None
    block: BlockCheckInput | None = None
    baseline_observations: tuple[tuple[Path, InputObservation], ...] = ()
    build_evidence: FinalBuildEvidence | None = None
    source_revision: int | None = None
    building: bool = False


@dataclass(frozen=True)
class CheckItem:
    rule_id: str
    title: str
    status: CheckStatus
    reason: str
    action: str
    scope: str
    input_id: str
    file: Path | None = None
    line: int | None = None


@dataclass(frozen=True)
class CheckReport:
    request_key: tuple
    input_id: str
    checked_at: float
    items: tuple[CheckItem, ...]
    observations: tuple[tuple[Path, InputObservation], ...]
    stable: bool
    word_count: WordCountResult | None = None
    watched_paths: tuple[Path, ...] = ()


class CheckCancelled(Exception):
    pass


def check_submission(request: CheckRequest, cancelled: Event | None = None) -> CheckReport:
    """Run in a worker. Identity covers bytes, buffers, engine and FINAL record."""
    def stop() -> None:
        if cancelled is not None and cancelled.is_set():
            raise CheckCancelled()

    stop()
    root, scope = request.root, request.scope
    root_ok = root is not None and scope is not None and safe_project_input(scope, root) == root
    profile_snapshot = load_profile(scope) if root_ok else None
    profile = profile_snapshot.profile if profile_snapshot and not profile_snapshot.error else None
    block = inspect_block_inputs(scope, request.block) if root_ok and request.block else None
    buffers = {b.path: b.text for b in request.buffers if b.path is not None}
    graph = static_dependencies(root, scope, buffers) if root_ok else None
    paths = set(graph.paths) if graph else set()
    paths.update(path for path in request.extra_inputs
                 if root_ok and safe_project_input(scope, path) is not None)
    if request.build_evidence and request.build_evidence.inputs:
        paths.update(path for path, _ in request.build_evidence.inputs.observations
                     if root_ok and safe_project_input(scope, path) is not None)
    observations = {}
    sources: dict[Path, str] = {}
    stable = True
    unreadable: list[Path] = []
    for path in sorted(paths):
        stop()
        observation = observe_input(path, scope)
        observations[path] = observation
        stable = stable and observation.stable
        if not observation.readable:
            unreadable.append(path)
        if path.suffix.lower() in SOURCE_SUFFIXES | {".bib"}:
            if path in buffers:
                sources[path] = buffers[path]
            elif observation.digest is not None:
                try:
                    sources[path] = read_project_source(path, scope)
                except (OSError, ValueError):
                    unreadable.append(path)
    identity = hashlib.sha256(repr((request.key, request.engine, request.tools,
                                    request.final, request.word_target, request.block, block,
                                    request.build_evidence, request.source_revision, request.building,
                                    profile_snapshot)).encode())
    for buffer in request.buffers:
        identity.update(repr((buffer.path, buffer.revision, buffer.modified)).encode())
        identity.update(buffer.text.encode("utf-8"))
    for path, observation in observations.items():
        identity.update(repr((path, observation)).encode())
    input_id = identity.hexdigest()
    items: list[CheckItem] = []

    def add(rule, title, status, reason, action="review", file=None, line=None):
        items.append(CheckItem(rule, title, status, reason, action,
                               str(root or "unsaved"), input_id, file, line))

    profile_unknown = bool(profile_snapshot and (profile_snapshot.error or not profile_snapshot.stable))
    add("project_profile", "项目配置", CheckStatus.UNKNOWN if profile_unknown else
        CheckStatus.PASS if profile and profile.enabled else CheckStatus.NOT_APPLICABLE,
        f"配置未能安全读取：{profile_snapshot.error or '读取期间发生变化'}；未把目标缺失当作通过。" if profile_unknown else
        "使用本地声明式配置；不是课程或学术认证。" if profile and profile.enabled else
        "项目配置已禁用，内容仍保留。" if profile else "未配置项目规则；不假定课程限制。", "profile")
    if profile and profile.enabled and profile.engine:
        matches = profile.engine == request.engine.value
        add("profile_engine", "配置引擎建议", CheckStatus.PASS if matches else CheckStatus.FAIL,
            f"配置建议 {profile.engine}，实际选择 {request.engine.value}；配置不会覆盖源码引擎声明。", "profile")

    pending_properties = bool(request.block and request.block.pending_property_drafts)
    dirty = (any(b.path is None or b.modified for b in request.buffers)
             or bool(block and block.saved is False) or pending_properties)
    saved_status = (CheckStatus.FAIL if dirty else
                    CheckStatus.UNKNOWN if block and block.saved is None else
                    CheckStatus.PASS if request.buffers or block else CheckStatus.UNKNOWN)
    add("saved", "保存状态", saved_status,
        "存在尚未应用的编辑草稿；磁盘和 PDF 不包含这些草稿。" if pending_properties else
        "存在未保存内容，或 Block 模型与磁盘元数据不一致。" if dirty else
        "当前 Block 模型与磁盘元数据一致。" if block and block.saved else
        "Block 元数据不可读；保存状态未知。" if block else
        "所捕获的项目编辑器均无待保存修改。", "review" if request.block else "save")
    if request.block:
        add("block_generated", "Block 生成源码", CheckStatus.PASS if block and block.generated is True else
            CheckStatus.FAIL if block and block.generated is False else CheckStatus.UNKNOWN,
            "磁盘生成源码与当前模型一致；检查未执行组装或写入。" if block and block.generated else
            "生成源码尚未确认与当前模型一致；可能存在模型修改或外部源码修改。")
    add("root", "编译入口", CheckStatus.PASS if root_ok and root in sources and observations[root].digest else CheckStatus.UNKNOWN,
        str(root.relative_to(scope)) if root_ok else "尚无安全、可读的项目编译入口。", "navigate", root, 1)
    # Revalidate captured tool paths without running TeX or invoking a shell.
    tools = replace(request.tools, **{
        field.name: value if value and Path(value).is_file() and os.access(value, os.X_OK) else None
        for field in fields(request.tools) for value in (getattr(request.tools, field.name),)
    })
    engine_ready = tools.supports_engine(request.engine)
    if request.engine == LaTeXEngine.AUTO and tools.latexmk:
        engine_ready = tools.pdflatex is not None
    add("toolchain", "LaTeX 环境", CheckStatus.PASS if engine_ready else CheckStatus.FAIL,
        f"{request.engine.display_name}：本地工具路径已检测；实际编译成功由正式构建项确认。"
        if engine_ready else f"未找到 {request.engine.display_name} 所需工具，请打开环境医生。", "environment")
    record = request.final
    evidence = request.build_evidence
    baseline = dict(evidence.inputs.observations) if evidence and evidence.inputs else {}
    inputs_match = bool(root in baseline and observations.get(root, InputObservation(None, False)).digest) and all(
        baseline.get(path) == observation for path, observation in observations.items()
        if observation.digest is not None or path in baseline
    ) and not unreadable and bool(evidence and evidence.inputs and evidence.inputs.stable)
    revision = request.source_revision if request.source_revision is not None else record.source_revision if record else None
    job = evidence.job_key if evidence else None
    identity_matches = bool(job and root_ok and job.root_file == root and job.purpose is BuildPurpose.FINAL
                            and job.source_revision == revision and job.engine == request.engine
                            and job.toolchain == request.tools
                            and (request.block or record and record.root_file == root
                                 and record.latest_build_id == evidence.build_id))
    building = request.building or bool(record and record.freshness == PdfFreshness.COMPILING)
    final_current = bool(identity_matches and inputs_match and evidence.outcome is CompileOutcome.SUCCESS
                         and saved_status is CheckStatus.PASS and not building
                         and (block and block.generated is True if request.block else
                              record.freshness == PdfFreshness.CURRENT
                              and record.last_successful_pdf == evidence.pdf_file
                              and record.last_successful_revision == record.source_revision))
    add("final_build", "正式构建", CheckStatus.CHECKING if building else CheckStatus.PASS if final_current else
        CheckStatus.UNKNOWN if evidence is None or evidence.inputs is None else CheckStatus.FAIL,
        f"FINAL 构建 {evidence.build_id}，输入 revision {job.source_revision}；构建前后输入摘要已复核。"
        if final_current else "正式构建正在进行；旧结果不代表当前输入。" if building else
        "尚无带输入证据的本会话 FINAL 构建。" if evidence is None else
        evidence.inputs.reason if evidence.inputs and not evidence.inputs.stable else
        "FINAL 的输入、模型 revision、引擎或保存状态与当前检查不一致，或构建未成功。",
        "review" if request.block else "compile")
    pdf = evidence.pdf_file if evidence else None
    pdf_observation = observe_input(pdf, scope, allow_internal=True) if root_ok and pdf else None
    pdf_ok = bool(pdf and root_ok and safe_project_input(scope, pdf, allow_internal=True)
                  and pdf.is_file() and pdf.stat().st_size > 0
                  and ".icstex" not in pdf.relative_to(scope).parts and evidence.inputs
                  and pdf_observation == evidence.inputs.pdf and pdf_observation.digest)
    add("pdf_current", "正式 PDF 新鲜度", CheckStatus.UNKNOWN if evidence is None else
        CheckStatus.PASS if final_current and pdf_ok else CheckStatus.FAIL,
        "当前 FINAL 的输入与 PDF 摘要一致；快速预览不参与此判断。" if final_current and pdf_ok
        else "没有与当前已保存输入匹配的 FINAL PDF；请正式编译。", "review" if request.block else "compile")
    log_current = bool(identity_matches and inputs_match and not dirty
                       and (not request.block or block and block.generated is True))
    add("final_log", "正式构建日志", CheckStatus.UNKNOWN if not log_current or not evidence.log_complete else
        CheckStatus.FAIL if evidence.errors or evidence.warnings else CheckStatus.PASS,
        "日志未确认属于当前输入，或日志证据不完整；不把旧日志当作当前诊断。" if not log_current or not evidence.log_complete else
        "当前 FINAL 日志含错误或引用/重跑警告。" if evidence.errors or evidence.warnings else
        "当前 FINAL 日志未解析到错误或引用/重跑警告；不是通用排版审计。")
    if log_current:
        for issue in (*evidence.errors, *evidence.warnings):
            location = safe_project_input(scope, issue.file) if issue.file else None
            add("final_log_issue", "正式构建诊断", CheckStatus.FAIL, issue.message,
                "navigate" if location else "review", location, issue.line)
    coverage = bool(graph and graph.complete and not unreadable)
    incomplete = not coverage or bool(graph and any(r.unresolved for r in graph.references))
    add("input_coverage", "检查覆盖范围", CheckStatus.UNKNOWN,
        "只解析常见静态引用并补充已有构建依赖；不解释任意宏，不保证课程或学术要求。"
        + (" 有超限、不可读或未解析输入。" if incomplete else ""))
    for path in dict.fromkeys(unreadable):
        add("input_unreadable", "输入不可读", CheckStatus.UNKNOWN,
            "路径或编码无法安全读取；未把缺失证据当作通过。", "navigate", path, 1)
    if graph:
        for ref in graph.references:
            if ref.unresolved:
                add("resource_unresolved", "资源引用未解析", CheckStatus.UNKNOWN,
                    f"{ref.command} 的动态或越界路径未读取：{ref.value}", "navigate", ref.source, ref.line)
            elif ref.command in {"input", "include", "subfile", "includegraphics", "bibliography", "addbibresource"}:
                if not any(observations.get(p, InputObservation(None, False)).digest is not None
                           or p in buffers for p in ref.candidates):
                    add("resource_missing", "缺少资源", CheckStatus.FAIL,
                        f"未找到 {ref.command} 引用的 {ref.value}。", "navigate", ref.source, ref.line)
    resource_issues = any(i.rule_id.startswith("resource_") for i in items)
    missing_resources = any(i.rule_id == "resource_missing" for i in items)
    add("resources", "静态资源", CheckStatus.FAIL if missing_resources else CheckStatus.UNKNOWN if resource_issues else
        CheckStatus.PASS if coverage else CheckStatus.UNKNOWN,
        "请查看逐项资源提示。" if resource_issues else "已检查可识别的图片、子文件和 BibTeX 路径。")
    ordered = sorted((p for p in sources if p.suffix.lower() in SOURCE_SUFFIXES), key=lambda p: (p != root, str(p)))
    lines: list[tuple[Path, int]] = []
    texts = []
    for path in ordered:
        text = strip_latex_comments(sources[path])
        parts = text.splitlines()
        texts.append("\n".join(parts) + "\n")
        lines.extend((path, n + 1) for n in range(len(parts)))
    combined = "".join(texts)
    bib = "\n".join(text for path, text in sources.items() if path.suffix.lower() == ".bib")
    diagnostics = reference_diagnostics(combined, bib, root_file=root)
    diagnostics += package_diagnostics(combined, root_file=root)
    for diagnostic in diagnostics:
        index = (diagnostic.line or 1) - 1
        location = lines[index] if 0 <= index < len(lines) else (root, 1)
        rule = {"未定义 ref": "reference_missing", "未定义 citation": "citation_missing",
                "重复 label": "label_duplicate"}.get(diagnostic.title, "package_hint")
        add(rule, diagnostic.title, CheckStatus.FAIL, diagnostic.message, "navigate", *location)
    add("references", "引用与标签", CheckStatus.FAIL if diagnostics else
        CheckStatus.PASS if coverage else CheckStatus.UNKNOWN,
        "存在需检查的静态诊断。" if diagnostics else "常见静态 citation/reference/label 未发现未解析项；不涵盖任意宏。")
    stop()
    count = count_project_snapshot(root, sources, request.tools) if root_ok and root in sources else None
    result = count.result if count else None
    count_current = count and count.stable and (not request.block or block and block.generated is True)
    add("word_count", "Word Count 口径", CheckStatus.PASS if count_current else CheckStatus.UNKNOWN,
        f"{result.effective_words} 正文字数；模式：{'TeXcount' if result.source == 'texcount' else 'Python fallback'}。"
        + (" 当前统计磁盘生成源码，尚不代表修改后的 Block 模型。" if request.block and not count_current else "")
        + (" ".join(result.warnings) if result else "") if result else "无法统计当前编译入口。", "word_count")
    word_target = profile.word_target if profile else request.word_target
    if profile_unknown:
        add("word_target", "字数目标", CheckStatus.UNKNOWN, "项目配置不可读；不能确认字数目标。", "profile")
    elif word_target is None:
        add("word_target", "字数目标", CheckStatus.NOT_APPLICABLE, "未配置字数目标；不假定任何课程上限。", "profile")
    else:
        low, high = word_target
        in_range = result is not None and (low is None or result.effective_words >= low) and (high is None or result.effective_words <= high)
        add("word_target", "字数目标", CheckStatus.UNKNOWN if not count_current else CheckStatus.PASS if in_range else CheckStatus.FAIL,
            f"用户目标：{low if low is not None else '不限'}–{high if high is not None else '不限'}；按正文字数比较。", "profile")
    if profile and profile.enabled:
        if not profile.check_resources:
            items[:] = [item for item in items if not item.rule_id.startswith("resource")]
            add("resources", "静态资源", CheckStatus.NOT_APPLICABLE,
                "用户关闭此项检查；不算通过，输入与 FINAL 安全检查仍保留。", "profile")
        if not profile.check_references:
            items[:] = [item for item in items if item.rule_id not in {
                "references", "reference_missing", "citation_missing", "label_duplicate", "package_hint"}]
            add("references", "引用与标签", CheckStatus.NOT_APPLICABLE,
                "用户关闭此项检查；不算通过，正式日志仍独立检查。", "profile")
    for path, observation in observations.items():
        stop()
        stable = stable and observe_input(path, scope) == observation
    if graph:
        stable = stable and static_dependencies(root, scope, sources) == graph
    stable = stable and (count is None or count.stable)
    stable = stable and (block is None or block_inputs_unchanged(scope, block))
    stable = stable and (pdf_observation is None or observe_input(pdf, scope, allow_internal=True) == pdf_observation)
    stable = stable and (profile_snapshot is None or profile_snapshot.stable and load_profile(scope) == profile_snapshot)
    watched = set(observations)
    if profile_snapshot:
        watched.add(profile_snapshot.path)
    if block:
        watched.update(path for path, _, internal in block.observations
                       if safe_project_input(scope, path, allow_internal=internal) is not None)
    return CheckReport(request.key, input_id, time(), tuple(items), tuple(observations.items()),
                       stable, result, tuple(sorted(watched)))
