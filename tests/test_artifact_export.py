"""Only a remembered, unchanged ordinary PDF may be atomically replaced."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.core.artifact_export import exported_pdf, pdf_export_destination, publish_exact_file
from app.core.project_checkpoint import CheckpointCancelled


class RememberedPdfTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.target = self.directory / 'export.pdf'
        publish_exact_file(self.target, b'old PDF', check_source=lambda: None)
        self.previous = exported_pdf(self.target, b'old PDF')

    def update(self, **kwargs):
        return publish_exact_file(self.target, b'new PDF', previous=self.previous,
                                  check_source=kwargs.pop('check_source', lambda: None), **kwargs)

    def test_replacement_is_opt_in_and_remembers_new_identity(self):
        with self.assertRaises(FileExistsError):
            publish_exact_file(self.target, b'new PDF', check_source=lambda: None)
        self.assertEqual(self.target.read_bytes(), b'old PDF')
        self.assertEqual(self.update(), self.target)
        current = exported_pdf(self.target, b'new PDF')
        self.assertNotEqual(current.signature, self.previous.signature)
        self.assertEqual(self.target.read_bytes(), b'new PDF')
        self.assertEqual(list(self.directory.glob('.icstex-export.incomplete-*')), [])

    def test_external_edit_and_identical_replacement_are_not_adopted(self):
        self.target.write_bytes(b'annotated PDF')
        with self.assertRaises(OSError):
            self.update()
        self.assertEqual(self.target.read_bytes(), b'annotated PDF')
        replacement = self.directory / 'replacement.pdf'
        replacement.write_bytes(b'old PDF')
        replacement.replace(self.target)
        with self.assertRaises(OSError):
            self.update()
        self.assertEqual(self.target.read_bytes(), b'old PDF')

    def test_missing_directory_and_symlink_are_not_recreated_or_followed(self):
        self.target.unlink()
        with self.assertRaises(OSError):
            self.update()
        self.target.mkdir()
        with self.assertRaises(OSError):
            self.update()
        self.target.rmdir()
        other = self.directory / 'unrelated.pdf'
        other.write_bytes(b'keep')
        self.target.symlink_to(other)
        with self.assertRaises(OSError):
            self.update()
        self.assertEqual(other.read_bytes(), b'keep')

    def test_staging_and_atomic_replace_failures_leave_old_pdf(self):
        for operation in ('os.fsync', 'os.replace'):
            with self.subTest(operation=operation), patch('app.core.artifact_export.' + operation,
                                                        side_effect=OSError('denied')):
                with self.assertRaises(OSError):
                    self.update()
            self.assertEqual(self.target.read_bytes(), b'old PDF')
            self.assertEqual(list(self.directory.glob('.icstex-export.incomplete-*')), [])

    def test_final_source_check_and_cancellation_preserve_old_file(self):
        def fail():
            raise ValueError('changed source')
        with self.assertRaises(ValueError):
            self.update(check_source=fail)
        cancelled = [False]
        with self.assertRaises(CheckpointCancelled):
            self.update(check_source=lambda: cancelled.__setitem__(0, True), cancelled=lambda: cancelled[0])
        self.assertEqual(self.target.read_bytes(), b'old PDF')
        self.assertEqual(list(self.directory.glob('.icstex-export.incomplete-*')), [])

    def test_destination_edit_during_source_check_is_preserved(self):
        with self.assertRaises(OSError):
            self.update(check_source=lambda: self.target.write_bytes(b'external late edit'))
        self.assertEqual(self.target.read_bytes(), b'external late edit')
        self.assertEqual(list(self.directory.glob('.icstex-export.incomplete-*')), [])

    def test_replaced_parent_is_not_used(self):
        nested = self.directory / 'folder'
        nested.mkdir()
        self.target = nested / 'export.pdf'
        self.target.write_bytes(b'old PDF')
        self.previous = exported_pdf(self.target, b'old PDF')
        nested.rename(self.directory / 'old-folder')
        nested.mkdir()
        self.target.write_bytes(b'old PDF')
        with self.assertRaises(OSError):
            self.update()
        self.assertEqual(self.target.read_bytes(), b'old PDF')

    def test_build_outputs_inputs_and_internal_aliases_are_not_export_destinations(self):
        from types import SimpleNamespace
        build = self.directory / '.latex_build'
        build.mkdir()
        image = self.directory / 'figure.pdf'
        proof = SimpleNamespace(pdf_file=build / 'main.pdf',
                                inputs=SimpleNamespace(observations=((image, None),)))
        alias = self.directory / 'alias'
        alias.symlink_to(build, target_is_directory=True)
        for target in (proof.pdf_file, image, alias / 'other.pdf'):
            with self.assertRaises(ValueError):
                pdf_export_destination(target, proof)
        self.assertEqual(pdf_export_destination(self.target, proof), self.target)
