from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.core.compiler import BuildPurpose, CompileOutcome, CompileResult
from app.core.latex_tools import LaTeXToolchain
from app.core.paths import preview_root_dir_for
from app.core.pdf_state import PdfFreshness
from app.core.preview_state import PreviewFreshness
from app.core.settings import AppSettings
from app.gui.main_window import EditorTab, MainWindow


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class GuiPreviewPipelineTests(TestCase):
    """Offscreen regression coverage for the preview/final build boundary."""

    def setUp(self) -> None:
        _app()
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name)
        settings = AppSettings(
            QSettings(
                str(self.directory / "settings.ini"),
                QSettings.Format.IniFormat,
            )
        )
        self.window = MainWindow(settings_store=settings)
        self.window._watch_file = lambda _path: None  # type: ignore[method-assign]
        self.window.auto_compile_action.setChecked(False)
        self.addCleanup(self._close_window)

    def _close_window(self) -> None:
        for tab in self.window.tabs.values():
            tab.modified = False
            tab.dirty = False
        self.window.close()

    def _add_document(self, text: str = "hello") -> EditorTab:
        source = self.directory / "main.tex"
        source.write_text(text, encoding="utf-8")
        tab = EditorTab(editor=self.window._make_editor(text), path=source)
        self.window._add_tab(tab, source.name)
        tab.manager = self.window.create_compile_manager(source)
        return tab

    def _result(
        self,
        tab: EditorTab,
        purpose: BuildPurpose,
        build_id: int,
        *,
        pdf_bytes: bytes = b"%PDF-1.4 pipeline-test",
    ) -> CompileResult:
        manager = tab.manager
        assert manager is not None
        output_dir = manager.output_dir_for(purpose)
        pdf_file = manager.pdf_file_for(purpose)
        output_dir.mkdir(parents=True, exist_ok=True)
        pdf_file.write_bytes(pdf_bytes)
        return CompileResult(
            root_file=manager.root_file,
            output_dir=output_dir,
            pdf_file=pdf_file,
            log_file=manager.log_file_for(purpose),
            command=[],
            returncode=0,
            stdout="",
            stderr="",
            duration_seconds=0.1,
            outcome=CompileOutcome.SUCCESS,
            build_id=build_id,
            purpose=purpose,
            preview_fidelity="proxy" if purpose is BuildPurpose.PREVIEW else None,
        )

    def _start(self, tab: EditorTab, purpose: BuildPurpose, build_id: int) -> None:
        manager = tab.manager
        assert manager is not None
        key = (manager.root_file, build_id)
        self.window.compile_build_owners[key] = manager
        self.window.compile_purposes[key] = purpose
        self.window.on_compile_started(str(manager.root_file), build_id)

    def _finish(self, result: CompileResult) -> None:
        with (
            patch.object(self.window, "run_project_check", return_value=[]),
            patch.object(self.window, "update_word_count"),
            patch.object(self.window, "_create_history_snapshot"),
        ):
            self.window.on_compile_finished(result)

    def _finish_success(
        self,
        tab: EditorTab,
        purpose: BuildPurpose,
        build_id: int,
    ) -> Path:
        result = self._result(tab, purpose, build_id)
        self._start(tab, purpose, build_id)
        self._finish(result)
        return result.pdf_file

    def test_preview_updates_only_preview_state_and_limits_pdf_actions(self) -> None:
        tab = self._add_document()
        manager = tab.manager
        assert manager is not None
        result = self._result(tab, BuildPurpose.PREVIEW, 1)

        self._start(tab, BuildPurpose.PREVIEW, 1)

        self.assertEqual(
            self.window.preview_state.record_for(manager.root_file).freshness,
            PreviewFreshness.COMPILING,
        )
        self.assertEqual(
            self.window.pdf_state.record_for(manager.root_file).freshness,
            PdfFreshness.UNCOMPILED,
        )

        self._finish(result)

        preview = self.window.preview_state.record_for(manager.root_file)
        canonical = self.window.pdf_state.record_for(manager.root_file)
        self.assertEqual(preview.freshness, PreviewFreshness.CURRENT)
        self.assertEqual(preview.last_successful_pdf, result.pdf_file.resolve())
        self.assertEqual(preview.fidelity, "proxy")
        self.assertEqual(canonical.freshness, PdfFreshness.UNCOMPILED)
        self.assertIsNone(canonical.last_successful_pdf)
        self.assertEqual(self.window.pdf_panel.current_pdf, result.pdf_file.resolve())
        self.assertEqual(
            self.window.displayed_pdfs[manager.root_file].purpose,
            BuildPurpose.PREVIEW,
        )
        self.assertTrue(self.window.export_pdf_action.isEnabled())
        self.assertTrue(self.window.pdf_panel.export_pdf_button.isEnabled())
        self.assertFalse(self.window.reveal_pdf_action.isEnabled())
        self.assertFalse(self.window.pdf_panel.reveal_pdf_button.isEnabled())
        self.assertFalse(self.window.sync_pdf_action.isEnabled())
        banner = self.window.pdf_panel.freshness_label.text()
        self.assertIn("快速预览", banner)
        self.assertIn("代理图", banner)
        self.assertIn("导出", banner)
        self.assertIn("原图", banner)

    def test_same_revision_final_success_replaces_preview_with_canonical_pdf(self) -> None:
        tab = self._add_document()
        manager = tab.manager
        assert manager is not None
        preview_pdf = self._finish_success(tab, BuildPurpose.PREVIEW, 1)

        final_pdf = self._finish_success(tab, BuildPurpose.FINAL, 2)

        preview = self.window.preview_state.record_for(manager.root_file)
        canonical = self.window.pdf_state.record_for(manager.root_file)
        self.assertEqual(preview.last_successful_revision, canonical.last_successful_revision)
        self.assertNotEqual(preview_pdf, final_pdf)
        self.assertEqual(canonical.freshness, PdfFreshness.CURRENT)
        self.assertEqual(self.window.pdf_panel.current_pdf, final_pdf.resolve())
        self.assertEqual(
            self.window.displayed_pdfs[manager.root_file].purpose,
            BuildPurpose.FINAL,
        )
        self.assertEqual(self.window.pdf_panel.freshness_label.text(), "PDF 已是最新")
        self.assertTrue(self.window.reveal_pdf_action.isEnabled())
        self.assertTrue(self.window.sync_pdf_action.isEnabled())

        self.window.pdf_state.mark_edited(manager.root_file)
        self.window._update_pdf_action_state()
        self.assertFalse(self.window.sync_pdf_action.isEnabled())

    def test_preview_only_export_queues_final_and_never_copies_preview_pdf(self) -> None:
        tab = self._add_document()
        manager = tab.manager
        assert manager is not None
        self._finish_success(tab, BuildPurpose.PREVIEW, 1)
        target = self.directory / "submission.pdf"

        with patch.object(manager, "compile_async") as compile_async, patch(
            "app.gui.main_window.QFileDialog.getSaveFileName",
            return_value=(str(target), ""),
        ):
            self.assertTrue(self.window.export_pdf())

        compile_async.assert_called_once_with(BuildPurpose.FINAL)
        self.assertFalse(target.exists())
        pending = self.window.pdf_export.pending_for(manager.root_file)
        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertEqual(pending.target, target.resolve())

    def test_idle_build_uses_preview_but_explicit_compile_defaults_to_final(self) -> None:
        tab = self._add_document()
        manager = tab.manager
        assert manager is not None
        self.assertTrue(self.window.preferences.fast_preview)
        self.window.toolchain = LaTeXToolchain(
            latexmk="/fake/latexmk",
            pdflatex="/fake/pdflatex",
        )
        self.window.compile_authorized_roots.add(manager.root_file)

        with (
            patch.object(manager, "compile_async") as compile_async,
        ):
            self.window.documents.compile_after_idle(tab)
            compile_async.assert_called_once_with(BuildPurpose.PREVIEW)

            compile_async.reset_mock()
            with patch.object(manager, "cancel_pending") as cancel_pending:
                self.window.compile_current(immediate=True)
                cancel_pending.assert_called_once_with()
                compile_async.assert_called_once_with(BuildPurpose.FINAL)

            compile_async.reset_mock()
            with patch.object(manager, "cancel_pending") as cancel_pending:
                self.window.compile.compile_current(immediate=True)
                cancel_pending.assert_called_once_with()
                compile_async.assert_called_once_with(BuildPurpose.FINAL)

    def test_external_image_change_dirties_both_states_and_queues_preview(self) -> None:
        tab = self._add_document()
        manager = tab.manager
        assert manager is not None
        root = manager.root_file
        image = (self.directory / "figures" / "plot.png").resolve()
        image.parent.mkdir()
        image.write_bytes(b"image")
        canonical_pdf = manager.pdf_file_for(BuildPurpose.FINAL)
        preview_pdf = manager.pdf_file_for(BuildPurpose.PREVIEW)
        canonical_pdf.parent.mkdir(parents=True, exist_ok=True)
        preview_pdf.parent.mkdir(parents=True, exist_ok=True)
        canonical_pdf.write_bytes(b"%PDF-1.4 canonical")
        preview_pdf.write_bytes(b"%PDF-1.4 preview")
        self.window.pdf_state.begin_build(root, 1)
        self.window.pdf_state.finish_build(
            root,
            1,
            CompileOutcome.SUCCESS,
            pdf_file=canonical_pdf,
        )
        self.window.preview_state.begin_build(root, 1)
        self.window.preview_state.finish_build(
            root,
            1,
            success=True,
            pdf_file=preview_pdf,
            fidelity="proxy",
        )
        self.window.preview_asset_roots[image] = {root}
        self.window.preview_root_assets[root] = {image}
        self.window.auto_compile_action.setChecked(True)

        with patch.object(manager, "schedule_compile") as schedule_compile:
            self.window.reload_external_change(str(image))

        canonical = self.window.pdf_state.record_for(root)
        preview = self.window.preview_state.record_for(root)
        self.assertEqual(canonical.freshness, PdfFreshness.DIRTY)
        self.assertEqual(preview.freshness, PreviewFreshness.DIRTY)
        self.assertEqual(canonical.source_revision, 1)
        self.assertEqual(preview.source_revision, 1)
        schedule_compile.assert_called_once_with("图片资源修改", BuildPurpose.PREVIEW)

        image.unlink()
        self.window.compile.register_preview_assets(root, ())
        self.assertIn(image, self.window.preview_asset_roots)
        image.write_bytes(b"restored-image")
        with patch.object(manager, "schedule_compile") as recreated_compile:
            self.window.reload_external_change(str(image))
        recreated_compile.assert_called_once_with("图片资源修改", BuildPurpose.PREVIEW)

    def test_clean_cache_removes_both_artifact_trees_and_clears_states(self) -> None:
        tab = self._add_document()
        manager = tab.manager
        assert manager is not None
        root = manager.root_file
        canonical_pdf = manager.pdf_file_for(BuildPurpose.FINAL)
        preview_pdf = manager.pdf_file_for(BuildPurpose.PREVIEW)
        canonical_pdf.parent.mkdir(parents=True, exist_ok=True)
        preview_pdf.parent.mkdir(parents=True, exist_ok=True)
        canonical_pdf.write_bytes(b"%PDF-1.4 canonical")
        preview_pdf.write_bytes(b"%PDF-1.4 preview")
        assets = preview_root_dir_for(root) / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        (assets / "plot.png").write_bytes(b"proxy")
        self.window.pdf_state.begin_build(root, 1)
        self.window.pdf_state.finish_build(
            root,
            1,
            CompileOutcome.SUCCESS,
            pdf_file=canonical_pdf,
        )
        self.window.preview_state.begin_build(root, 1)
        self.window.preview_state.finish_build(
            root,
            1,
            success=True,
            pdf_file=preview_pdf,
            fidelity="proxy",
        )
        self.window._sync_pdf_panel_to_active_root()

        self.assertTrue(self.window.clean_build_cache())

        self.assertFalse(manager.output_dir.exists())
        self.assertFalse(preview_root_dir_for(root).exists())
        canonical = self.window.pdf_state.record_for(root)
        preview = self.window.preview_state.record_for(root)
        self.assertEqual(canonical.freshness, PdfFreshness.UNCOMPILED)
        self.assertEqual(preview.freshness, PreviewFreshness.UNCOMPILED)
        self.assertFalse(canonical.has_valid_pdf)
        self.assertFalse(preview.has_valid_pdf)
        self.assertNotIn(root, self.window.displayed_pdfs)
        self.assertIsNone(self.window.pdf_panel.current_pdf)
        self.assertFalse(self.window.export_pdf_action.isEnabled())
