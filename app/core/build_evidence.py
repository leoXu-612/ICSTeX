"""Bounded, immutable input/output evidence for an actual local compile job."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.log_parser import LaTeXError
from app.core.project_dependencies import (InputObservation, MAX_INPUTS, observe_input,
                                         safe_project_input, static_dependencies)

if TYPE_CHECKING:
    from app.core.compiler import CompileJobKey, CompileOutcome, CompileResult


@dataclass(frozen=True)
class InputSnapshot:
    observations: tuple[tuple[Path, InputObservation], ...]
    complete: bool


@dataclass(frozen=True)
class BuildInputEvidence:
    observations: tuple[tuple[Path, InputObservation], ...]
    stable: bool
    pdf: InputObservation | None
    reason: str


def capture_compile_inputs(root: Path, scope: Path, extra: tuple[Path, ...] = ()) -> InputSnapshot:
    graph = static_dependencies(root, scope)
    paths = set(graph.paths)
    paths.update(path for path in extra if safe_project_input(scope, path) is not None)
    complete = graph.complete and len(paths) <= MAX_INPUTS
    observations = tuple((path, observe_input(path, scope)) for path in sorted(paths)[:MAX_INPUTS])
    complete = complete and all(value.stable and value.readable for _, value in observations)
    return InputSnapshot(observations, complete)


def finish_compile_inputs(before: InputSnapshot, root: Path, scope: Path,
                          recorded: tuple[Path, ...], pdf: Path | None) -> BuildInputEvidence:
    # Retain old candidates too, so removal/disappearance cannot silently shrink proof.
    after = capture_compile_inputs(root, scope, (*recorded, *(path for path, _ in before.observations)))
    stable = before.complete and after.complete and before.observations == after.observations
    stable = bool(stable and dict(after.observations).get(root, InputObservation(None, False)).digest)
    output = observe_input(pdf, scope, allow_internal=True) if pdf is not None else None
    stable = bool(stable and (output is None or output.stable and output.readable and output.digest))
    return BuildInputEvidence(after.observations, stable, output,
                              "实际构建前后已知输入摘要一致。" if stable else
                              "构建期间输入变化、出现新依赖或证据不完整；请重新正式编译。")


@dataclass(frozen=True)
class FinalBuildEvidence:
    """Small result view; never retains mutable widgets or unbounded console output."""
    job_key: CompileJobKey
    build_id: int
    outcome: CompileOutcome
    pdf_file: Path
    inputs: BuildInputEvidence | None
    errors: tuple[LaTeXError, ...]
    warnings: tuple[LaTeXError, ...]
    log_complete: bool


def final_build_evidence(result: CompileResult) -> FinalBuildEvidence | None:
    if result.job_key is None or result.purpose.value != "final" or result.job_key.purpose.value != "final":
        return None
    return FinalBuildEvidence(result.job_key, result.build_id, result.outcome, result.pdf_file,
                              result.input_evidence, tuple(result.errors), result.warnings, result.log_complete)
