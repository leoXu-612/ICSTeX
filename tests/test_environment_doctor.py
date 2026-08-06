from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app.core.diagnostics import Diagnostic
from app.core.environment_doctor import (
    FEEDBACK_LOG_MAX_CHARS,
    FEEDBACK_LOG_TAIL_LINES,
    FeedbackMetadata,
    build_environment_report,
    build_feedback_bundle,
)
from app.core.latex_tools import LaTeXToolchain


class EnvironmentDoctorTests(TestCase):
    def test_report_warns_when_compile_tools_are_missing(self) -> None:
        toolchain = LaTeXToolchain(latexmk=None, pdflatex=None, xelatex=None, lualatex=None)

        with patch("app.core.environment_doctor.which", return_value=None):
            report = build_environment_report(toolchain)

        self.assertFalse(report.compile_ready)
        self.assertIn("未找到 LaTeX 编译器", report.as_text())
        self.assertIn("未找到 texcount", report.as_text())

    def test_report_lists_available_tools_and_versions(self) -> None:
        toolchain = LaTeXToolchain(
            latexmk="/texbin/latexmk",
            pdflatex="/texbin/pdflatex",
            xelatex=None,
            lualatex=None,
            biber="/texbin/biber",
            bibtex=None,
            texcount="/texbin/texcount",
            synctex="/texbin/synctex",
        )

        with patch("app.core.environment_doctor.which", return_value=None), patch(
            "app.core.environment_doctor._tool_version", return_value="fake version"
        ):
            report = build_environment_report(toolchain)

        self.assertTrue(report.compile_ready)
        text = report.as_text()
        self.assertIn("latexmk", text)
        self.assertIn("fake version", text)
        self.assertIn("编译核心可用", text)


class FeedbackBundleTests(TestCase):
    def _report(self) -> object:
        toolchain = LaTeXToolchain(latexmk=None, pdflatex=None, xelatex=None, lualatex=None)
        with patch("app.core.environment_doctor.which", return_value=None):
            return build_environment_report(toolchain)

    def test_bundle_includes_privacy_notice_and_environment_report(self) -> None:
        bundle = build_feedback_bundle(self._report())

        self.assertIn("反馈包", bundle)
        self.assertIn("不含论文正文", bundle)
        self.assertIn("环境诊断报告", bundle)

    def test_bundle_redacts_project_path_to_file_name(self) -> None:
        bundle = build_feedback_bundle(
            self._report(),
            project_file=Path("/Users/student/SuperSecretThesis/main.tex"),
            metadata=FeedbackMetadata(
                selected_engine="XeLaTeX",
                root_file=Path("/Users/student/SuperSecretThesis/main.tex"),
                root_source="magic comment",
                latest_compile_seconds=12.345,
                word_count_mode="Python 简化统计",
            ),
        )

        self.assertIn("main.tex", bundle)
        self.assertIn("XeLaTeX", bundle)
        self.assertIn("magic comment", bundle)
        self.assertIn("12.35s", bundle)
        self.assertIn("Python 简化统计", bundle)
        self.assertNotIn("SuperSecretThesis", bundle)
        self.assertNotIn("/Users/student", bundle)

    def test_bundle_redacts_absolute_paths_in_compile_log(self) -> None:
        # A real latexmk log embeds absolute paths (username + project dir name);
        # those must not survive into the shared bundle even though basenames may.
        project_file = Path("/Users/student/SuperSecretThesis/main.tex")
        log = (
            "Latexmk: applying rule 'pdflatex'...\n"
            "This is pdfTeX, Output written on "
            "/Users/student/SuperSecretThesis/.latex_build/main.pdf (1 page).\n"
            "(/Users/student/SuperSecretThesis/main.tex line 12)\n"
        )

        bundle = build_feedback_bundle(self._report(), recent_log=log, project_file=project_file)

        self.assertNotIn("SuperSecretThesis", bundle)
        self.assertNotIn("/Users/student", bundle)
        self.assertIn("<project>", bundle)
        self.assertIn("main.tex", bundle)  # basename still useful for debugging

    def test_bundle_summarises_diagnostics_with_filenames_only(self) -> None:
        diagnostics = [
            Diagnostic(
                severity="error",
                title="缺少 graphicx",
                message="插入图片需要 graphicx package。",
                file=Path("/Users/student/work/main.tex"),
                line=12,
            ),
            Diagnostic(
                severity="warning",
                title="未引用的 label",
                message="label 没有被引用。",
            ),
        ]

        bundle = build_feedback_bundle(self._report(), diagnostics=diagnostics)

        self.assertIn("项目检查摘要", bundle)
        self.assertIn("[错误] 缺少 graphicx", bundle)
        self.assertIn("（main.tex:12）", bundle)
        self.assertIn("[警告] 未引用的 label", bundle)
        self.assertNotIn("/Users/student", bundle)

    def test_bundle_truncates_long_log_to_tail(self) -> None:
        long_log = "\n".join(f"line {index}" for index in range(FEEDBACK_LOG_TAIL_LINES * 3))

        bundle = build_feedback_bundle(self._report(), recent_log=long_log)

        self.assertIn(f"末尾 {FEEDBACK_LOG_TAIL_LINES} 行", bundle)
        self.assertIn(f"line {FEEDBACK_LOG_TAIL_LINES * 3 - 1}", bundle)
        self.assertNotIn("line 0\n", bundle)

    def test_bundle_caps_log_character_length(self) -> None:
        long_line = "x" * (FEEDBACK_LOG_MAX_CHARS * 2)

        bundle = build_feedback_bundle(self._report(), recent_log=long_line)

        # The truncated tail line plus the leading "… " marker should appear.
        self.assertIn("… ", bundle)
        # Bundle text overall stays bounded near the cap (plus header lines).
        self.assertLess(len(bundle), FEEDBACK_LOG_MAX_CHARS + 2000)

    def test_bundle_omits_empty_sections(self) -> None:
        bundle = build_feedback_bundle(self._report())

        self.assertNotIn("项目检查摘要", bundle)
        self.assertNotIn("最近编译日志", bundle)
        self.assertNotIn("当前项目", bundle)
