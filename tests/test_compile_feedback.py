from __future__ import annotations

from pathlib import Path
from unittest import TestCase

from app.core.compile_feedback import headline_for, presentation_for
from app.core.compiler import CompileOutcome, CompileResult
from app.core.log_parser import LaTeXError


def _result(outcome: CompileOutcome, **overrides: object) -> CompileResult:
    root = Path("/projects/thesis/main.tex")
    values: dict = dict(
        root_file=root,
        output_dir=root.parent / ".latex_build",
        pdf_file=root.parent / ".latex_build" / "main.pdf",
        log_file=root.parent / ".latex_build" / "main.log",
        command=[],
        returncode=0,
        stdout="",
        stderr="",
        duration_seconds=2.34,
        outcome=outcome,
        errors=[],
        build_id=1,
    )
    values.update(overrides)
    return CompileResult(**values)


class CompileFeedbackTests(TestCase):
    def test_every_outcome_has_a_complete_presentation(self) -> None:
        for outcome in CompileOutcome:
            presentation = presentation_for(outcome)
            self.assertTrue(presentation.title)
            self.assertTrue(presentation.detail)
            self.assertTrue(presentation.next_action)
            self.assertIn(presentation.severity, {"success", "warning", "error"})

    def test_expected_titles(self) -> None:
        self.assertEqual(presentation_for(CompileOutcome.SUCCESS).title, "编译成功")
        self.assertEqual(presentation_for(CompileOutcome.STOPPED).title, "编译已停止")
        self.assertEqual(
            presentation_for(CompileOutcome.TOOLCHAIN_MISSING).title, "未找到可用的 LaTeX 编译器"
        )
        self.assertEqual(
            presentation_for(CompileOutcome.ROOT_FILE_MISSING).title, "根 LaTeX 文件不存在"
        )
        self.assertEqual(
            presentation_for(CompileOutcome.PROCESS_START_FAILED).title, "无法启动编译进程"
        )
        self.assertEqual(
            presentation_for(CompileOutcome.OUTPUT_MISSING).title, "编译结束，但没有生成有效 PDF"
        )
        self.assertEqual(
            presentation_for(CompileOutcome.INTERNAL_ERROR).title,
            "ICSTeX 处理编译结果时发生错误",
        )

    def test_success_headline_uses_root_name_engine_and_duration(self) -> None:
        headline = headline_for(_result(CompileOutcome.SUCCESS), engine_name="XeLaTeX")
        self.assertIn("编译成功", headline)
        self.assertIn("main.tex", headline)
        self.assertIn("XeLaTeX", headline)
        self.assertIn("2.34s", headline)
        self.assertNotIn("/projects/thesis", headline)

    def test_latex_error_headline_leads_with_first_actionable_diagnostic(self) -> None:
        footer = "Latexmk: Errors, so did not complete cycle"
        result = _result(
            CompileOutcome.LATEX_ERROR,
            returncode=12,
            stderr=footer,
            errors=[
                LaTeXError(message="Undefined control sequence \\foo", line=3),
                LaTeXError(message="Missing $ inserted", line=9),
            ],
        )
        headline = headline_for(result)
        self.assertTrue(headline.startswith("编译失败："))
        self.assertNotIn("Latexmk", headline)
        self.assertNotIn("/projects/thesis", headline)

    def test_process_start_failed_headline_includes_first_os_error_line(self) -> None:
        result = _result(
            CompileOutcome.PROCESS_START_FAILED,
            returncode=126,
            stderr="[Errno 13] Permission denied: 'pdflatex'\nsecond line",
        )
        headline = headline_for(result)
        self.assertIn("无法启动编译进程", headline)
        self.assertIn("Permission denied", headline)
        self.assertNotIn("second line", headline)

    def test_other_outcomes_use_root_filename_not_absolute_path(self) -> None:
        for outcome in (
            CompileOutcome.STOPPED,
            CompileOutcome.TOOLCHAIN_MISSING,
            CompileOutcome.ROOT_FILE_MISSING,
            CompileOutcome.OUTPUT_MISSING,
            CompileOutcome.INTERNAL_ERROR,
        ):
            headline = headline_for(_result(outcome, returncode=1))
            self.assertIn("main.tex", headline)
            self.assertNotIn("/projects/thesis", headline)
