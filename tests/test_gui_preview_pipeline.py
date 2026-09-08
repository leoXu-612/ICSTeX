from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.compiler import BuildPurpose, CompileOutcome, CompileResult
from app.core.latex_tools import LaTeXEngine, LaTeXToolchain
from app.core.paths import preview_root_dir_for
from app.core.pdf_state import PdfFreshness
from app.core.preview_state import PreviewFreshness
from app.core.settings import AppSettings
from app.core.synctex import SyncPosition, source_to_pdf
from app.gui.main_window import EditorTab, MainWindow


def _app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def _wait_until(predicate) -> bool:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class GuiPreviewPipelineTests(TestCase):
    """Offscreen regression coverage for the preview/final build boundary."""

    def setUp(self) -> None:
        _app()
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.directory = Path(self._tmp.name).resolve()
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
        self.window.pdf_panel.clear_pdf()
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

    def test_reverse_sync_uses_current_preview_instead_of_stale_final(self) -> None:
        tab = self._add_document()
        self._finish_success(tab, BuildPurpose.FINAL, 1)
        self.window._mark_source_edited(tab)
        preview_pdf = self._finish_success(tab, BuildPurpose.PREVIEW, 2)
        self.window.toolchain = replace(self.window.toolchain, synctex="synctex")
        root = tab.manager.root_file
        with (
            patch("app.gui.main_window.pdf_to_source", return_value=SyncPosition(root, 1)) as query,
            patch.object(self.window, "open_file") as open_file,
        ):
            self.window.sync_pdf_to_source(1, 10.0, 20.0)
        query.assert_called_once_with(
            preview_pdf, 1, 10.0, 20.0, self.window.toolchain, source_directory=root.parent,
        )
        open_file.assert_called_once_with(root, 1)
        self.assertFalse(self.window.sync_pdf_action.isEnabled())

    def test_reverse_sync_retains_current_final_navigation(self) -> None:
        tab = self._add_document()
        self._finish_success(tab, BuildPurpose.PREVIEW, 1)
        final_pdf = self._finish_success(tab, BuildPurpose.FINAL, 2)
        self.window.toolchain = replace(self.window.toolchain, synctex="synctex")
        root = tab.manager.root_file
        with (
            patch("app.gui.main_window.pdf_to_source", return_value=SyncPosition(root, 1)) as query,
            patch.object(self.window, "open_file") as open_file,
        ):
            self.window.sync_pdf_to_source(1, 10.0, 20.0)
        self.assertEqual(query.call_args.args[0], final_pdf)
        open_file.assert_called_once_with(root, 1)

    def test_reverse_sync_rejects_stale_busy_and_mismatched_preview(self) -> None:
        tab = self._add_document()
        self._finish_success(tab, BuildPurpose.PREVIEW, 1)
        root = tab.manager.root_file
        record = self.window.preview_state.record_for(root)
        cases = [
            (record, "freshness", freshness)
            for freshness in (
                PreviewFreshness.DIRTY, PreviewFreshness.COMPILING,
                PreviewFreshness.FAILED_STALE, PreviewFreshness.UNCOMPILED,
            )
        ] + [
            (record, "source_revision", record.source_revision + 1),
            (record, "latest_build_id", 2),
            (record, "last_successful_pdf", root.parent / "different.pdf"),
            (self.window.pdf_panel, "current_pdf", root.parent / "different.pdf"),
            (self.window.pdf_panel, "current_logical_key", root.parent / "different.tex"),
        ]
        for target, attribute, value in cases:
            with (
                self.subTest(attribute=attribute, value=value),
                patch.object(target, attribute, value),
                patch("app.gui.main_window.pdf_to_source") as query,
            ):
                self.window.sync_pdf_to_source(1, 10.0, 20.0)
                query.assert_not_called()
        displayed = self.window.displayed_pdfs[root]
        for changed in (
            replace(displayed, revision=displayed.revision + 1),
            replace(displayed, build_id=None),
            replace(displayed, root_file=root.parent / "different.tex"),
        ):
            with (
                self.subTest(displayed=changed),
                patch.dict(self.window.displayed_pdfs, {root: changed}),
                patch("app.gui.main_window.pdf_to_source") as query,
            ):
                self.window.sync_pdf_to_source(1, 10.0, 20.0)
                query.assert_not_called()

    def test_same_revision_rebuild_reloads_pdf_for_matching_synctex(self) -> None:
        tab = self._add_document()
        for purpose, first, second in ((BuildPurpose.PREVIEW, 1, 2), (BuildPurpose.FINAL, 3, 4)):
            with self.subTest(purpose=purpose):
                self._finish_success(tab, purpose, first)
                with patch.object(self.window.pdf_panel, "load_pdf") as reload_pdf:
                    pdf = self._finish_success(tab, purpose, second)
                reload_pdf.assert_called_once_with(pdf, logical_key=tab.manager.root_file)
                self.assertEqual(self.window.displayed_pdfs[tab.manager.root_file].build_id, second)

    def test_preview_reverse_sync_refuses_missing_tool_data_or_unsafe_target(self) -> None:
        tab = self._add_document()
        pdf = self._finish_success(tab, BuildPurpose.PREVIEW, 1)
        self.window.toolchain = replace(self.window.toolchain, synctex=None)
        with patch("app.gui.main_window.pdf_to_source") as query:
            self.window.sync_pdf_to_source(1, 10, 20)
        query.assert_not_called()
        self.window.toolchain = replace(self.window.toolchain, synctex="synctex")
        for position in (None, SyncPosition(self.directory.parent / "outside.tex", 1)):
            with (
                self.subTest(position=position),
                patch("app.gui.main_window.pdf_to_source", return_value=position),
                patch.object(self.window, "open_file") as open_file,
            ):
                self.window.sync_pdf_to_source(1, 10, 20)
                open_file.assert_not_called()
        pdf.unlink()
        with patch("app.gui.main_window.pdf_to_source") as query:
            self.window.sync_pdf_to_source(1, 10, 20)
        query.assert_not_called()

    def test_preview_reverse_sync_opens_original_child_and_preserves_root(self) -> None:
        child = self.directory / "chapters" / "body.tex"
        child.parent.mkdir()
        child.write_text("% !TEX root = ../main.tex\nFirst line.\nTarget line.\n", encoding="utf-8")
        tab = self._add_document("\\documentclass{article}\n\\input{chapters/body}\n")
        pdf = self._finish_success(tab, BuildPurpose.PREVIEW, 1)
        self.window.toolchain = replace(self.window.toolchain, synctex="synctex")
        root = tab.manager.root_file
        with patch("app.gui.main_window.pdf_to_source", return_value=SyncPosition(child.resolve(), 3)):
            self.window.sync_pdf_to_source(1, 10, 20)
        current = self.window.current_tab()
        self.assertEqual(current.path, child.resolve())
        self.assertEqual(current.editor.textCursor().blockNumber() + 1, 3)
        self.assertEqual(self.window._compile_root_for_tab(current), root)
        self.assertEqual(self.window.pdf_panel.current_pdf, pdf)

    def test_foreign_active_tab_cannot_reverse_sync_from_cached_preview(self) -> None:
        tab = self._add_document()
        preview = self._finish_success(tab, BuildPurpose.PREVIEW, 1)
        other = self.directory / "other.tex"
        other.write_text("Other document", encoding="utf-8")
        self.window.open_file(other)
        self.window.pdf_panel.current_pdf = preview
        self.window.pdf_panel.current_logical_key = tab.manager.root_file
        with patch("app.gui.main_window.pdf_to_source") as query:
            self.window.sync_pdf_to_source(1, 10, 20)
        query.assert_not_called()

    def test_reverse_sync_guards_worker_start_before_queued_gui_signal(self) -> None:
        tab = self._add_document()
        self._finish_success(tab, BuildPurpose.PREVIEW, 1)
        root = tab.manager.root_file
        self.window.toolchain = replace(self.window.toolchain, synctex="synctex")
        key = (root, 2)
        # FINAL writes a separate output; it does not invalidate a current preview.
        for purpose, allowed in ((BuildPurpose.FINAL, True), (BuildPurpose.PREVIEW, False)):
            with (
                self.subTest(purpose=purpose),
                patch.dict(self.window.compile_purposes, {key: purpose}),
                patch("app.gui.main_window.pdf_to_source", return_value=None) as query,
            ):
                self.window.sync_pdf_to_source(1, 10, 20)
                self.assertEqual(query.called, allowed)

        def start_during_query(*args, **kwargs):
            self.window.compile_purposes[key] = BuildPurpose.PREVIEW
            return SyncPosition(root, 1)

        with (
            patch("app.gui.main_window.pdf_to_source", side_effect=start_during_query),
            patch.object(self.window, "open_file") as open_file,
        ):
            self.window.sync_pdf_to_source(1, 10, 20)
        open_file.assert_not_called()
        self.window.compile_purposes.pop(key)

    def test_real_preview_double_click_maps_original_child(self) -> None:
        if not self.window.toolchain.pdflatex or not self.window.toolchain.synctex:
            self.skipTest("Real preview SyncTeX requires local pdfLaTeX and synctex")
        panel = self.window.pdf_panel
        if panel._view is None:
            self.skipTest("QtPdf is unavailable")
        child = self.directory / "chapters" / "body.tex"
        child.parent.mkdir()
        child_text = (
            "% !TEX root = ../main.tex\n"
            "\\noindent Original child target for preview reverse SyncTeX.\\par\n"
        )
        child.write_text(child_text, encoding="utf-8")
        picture = QImage(2400, 1600, QImage.Format.Format_RGB32)
        picture.fill(Qt.GlobalColor.blue)
        self.assertTrue(picture.save(str(self.directory / "figure.png")))
        source_text = (
            "\\documentclass{article}\n\\usepackage{graphicx}\n\\begin{document}\n"
            "Root page with a proxy image.\\par\n"
            "\\includegraphics[width=4cm]{figure.png}\n"
            "\\newpage\n\\input{chapters/body}\n\\end{document}\n"
        )
        self.window.current_engine = LaTeXEngine.PDFLATEX
        tab = self._add_document(source_text)
        self.window.show()
        manager = tab.manager
        assert manager is not None
        with (
            patch.object(self.window, "run_project_check", return_value=[]),
            patch.object(self.window, "update_word_count"),
            patch.object(self.window, "_create_history_snapshot"),
        ):
            result = manager.compile_now(BuildPurpose.PREVIEW, timeout_seconds=30)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertTrue(result.ok, result.stdout + result.stderr)
            self.assertEqual(result.preview_fidelity, "proxy")
            self.assertTrue(_wait_until(lambda: panel._document.pageCount() == 2))
            QTest.qWait(150)
            self.assertEqual(panel.current_pdf, result.pdf_file)
            self.assertTrue(result.pdf_file.with_suffix(".synctex.gz").is_file())
            self.assertFalse(manager.pdf_file.exists())
            target = source_to_pdf(child.resolve(), 2, result.pdf_file, self.window.toolchain)
            self.assertIsNotNone(target)
            assert target is not None
            self.assertEqual(target.page, 2)
            assert target.x is not None and target.y is not None
            for zoom in (0.9, 1.25):
                with self.subTest(zoom=zoom):
                    self.window.open_file(manager.root_file, 1)
                    panel._view.setZoomMode(panel._view.ZoomMode.Custom)
                    panel._view.setZoomFactor(zoom)
                    panel.jump_to_pdf_position(2, target.x, target.y)
                    QApplication.processEvents()
                    geometry = panel._page_geometry(1)
                    assert geometry is not None
                    left, top, _width, _height, scale = geometry
                    point = QPoint(
                        round(left + (target.x + 2) * scale - panel._view.horizontalScrollBar().value()),
                        round(top + (target.y - 2) * scale - panel._view.verticalScrollBar().value()),
                    )
                    self.assertTrue(panel._view.viewport().rect().contains(point))
                    QTest.mouseDClick(panel._view.viewport(), Qt.MouseButton.LeftButton, pos=point)
                    current = self.window.current_tab()
                    self.assertEqual(current.path, child.resolve())
                    self.assertEqual(current.editor.textCursor().blockNumber() + 1, 2)
                    self.assertEqual(self.window._compile_root_for_tab(current), manager.root_file)
                    self.assertEqual(panel.current_pdf, result.pdf_file)
                    self.assertEqual(len(self.window.tabs), 2)
        self.assertEqual(child.read_text(encoding="utf-8"), child_text)
        self.assertEqual(tab.path.read_text(encoding="utf-8"), source_text)

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
        self.window.auto_compile_action.setChecked(True)

        with (
            patch.object(manager, "compile_async") as compile_async,
        ):
            self.window.documents.compile_after_idle(tab)
            compile_async.assert_called_once_with(BuildPurpose.PREVIEW)

            self.window.auto_compile_action.setChecked(False)
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
        self.window.compile.register_preview_assets(root, (image,))
        self.assertTrue(_wait_until(lambda: not self.window.dependencies.is_busy))
        self.window.auto_compile_action.setChecked(True)
        self.window.compile_authorized_roots.add(root)

        with patch.object(manager, "schedule_compile") as schedule_compile:
            image.write_bytes(b"changed-image")
            self.window.reload_external_change(str(image))
            self.assertTrue(_wait_until(lambda: not self.window.dependencies.is_busy))

        canonical = self.window.pdf_state.record_for(root)
        preview = self.window.preview_state.record_for(root)
        self.assertEqual(canonical.freshness, PdfFreshness.DIRTY)
        self.assertEqual(preview.freshness, PreviewFreshness.DIRTY)
        self.assertEqual(canonical.source_revision, 1)
        self.assertEqual(preview.source_revision, 1)
        schedule_compile.assert_called_once_with("输入依赖修改", BuildPurpose.PREVIEW)

        image.unlink()
        self.window.compile.register_preview_assets(root, ())
        self.assertIn(image, self.window.preview_asset_roots)
        image.write_bytes(b"restored-image")
        with patch.object(manager, "schedule_compile") as recreated_compile:
            self.window.reload_external_change(str(image))
            self.assertTrue(_wait_until(lambda: not self.window.dependencies.is_busy))
        recreated_compile.assert_called_once_with("输入依赖修改", BuildPurpose.PREVIEW)

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
