from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.gui.drop_import_worker import DropCopyWorker


def app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class DropCopyWorkerTests(TestCase):
    def setUp(self) -> None:
        app()
        self.main_thread_id = threading.get_ident()

    def _run_worker(self, project: Path, tex: Path, sources: list[str]) -> tuple[list, DropCopyWorker]:
        worker = DropCopyWorker(project, tex, sources)
        results: list = []
        worker.completed.connect(results.extend)
        worker.start()
        self.assertTrue(worker.wait(5000))
        QApplication.processEvents()
        return results, worker

    def test_copies_external_images_in_background_thread(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (outside / "a.png").write_bytes(b"a")
            (outside / "b.jpg").write_bytes(b"b")
            tex = project / "main.tex"
            tex.write_text("\\documentclass{article}\n", encoding="utf-8")

            results, worker = self._run_worker(project, tex, [str(outside / "a.png"), str(outside / "b.jpg")])

            self.assertEqual(len(results), 2)
            self.assertTrue(all(result.error is None for result in results))
            self.assertTrue((project / "figures" / "a.png").exists())
            self.assertTrue((project / "figures" / "b.jpg").exists())
            self.assertEqual(results[0].relative_path, "figures/a.png")
            self.assertIsNotNone(worker.thread_id)
            self.assertNotEqual(worker.thread_id, self.main_thread_id)

    def test_rejects_unsupported_and_missing_sources(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            tex = project / "main.tex"

            results, _worker = self._run_worker(
                project,
                tex,
                [str(root / "notes.txt"), str(root / "missing.png")],
            )

            self.assertEqual(len(results), 2)
            self.assertTrue(all(result.error is not None for result in results))
            self.assertTrue(all(result.destination is None for result in results))

    def test_reuses_project_internal_source_without_copy(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory)
            image = project / "existing.png"
            image.write_bytes(b"x")
            tex = project / "main.tex"

            results, _worker = self._run_worker(project, tex, [str(image)])

            self.assertEqual(len(results), 1)
            self.assertIsNone(results[0].error)
            self.assertEqual(results[0].relative_path, "existing.png")
            self.assertEqual(results[0].destination, image)
            self.assertFalse((project / "figures").exists())
