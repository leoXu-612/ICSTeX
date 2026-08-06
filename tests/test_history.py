from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.history import create_snapshot, list_snapshots, read_snapshot


class HistoryTests(TestCase):
    def test_create_list_and_read_snapshot(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("A", encoding="utf-8")

            first = create_snapshot(source, "A", "保存")
            duplicate = create_snapshot(source, "A", "保存")
            second = create_snapshot(source, "B", "编译成功")

            snapshots = list_snapshots(source)

            self.assertIsNotNone(first)
            self.assertIsNone(duplicate)
            self.assertIsNotNone(second)
            self.assertEqual([snapshot.label for snapshot in snapshots], ["编译成功", "保存"])
            self.assertEqual(read_snapshot(snapshots[0]), "B")

    def test_corrupt_snapshot_is_not_decoded_with_replacement_characters(self) -> None:
        with TemporaryDirectory() as directory:
            source = Path(directory) / "main.tex"
            source.write_text("Original", encoding="utf-8")
            snapshot = create_snapshot(source, "Original", "保存")
            assert snapshot is not None
            snapshot.snapshot_path.write_bytes(b"Corrupt \xff")

            with self.assertRaises(UnicodeDecodeError):
                read_snapshot(snapshot)
