from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.core.project_file_ops import (
    ProjectFileOperationError,
    execute_project_path_move,
    find_move_blockers,
    plan_project_path_move,
    remap_moved_path,
    rename_destination,
)


class ProjectFileOperationTests(TestCase):
    def test_plan_rejects_escape_collision_root_and_descendant(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            source = root / "chapter.tex"
            source.write_text("chapter", encoding="utf-8")
            collision = root / "existing.tex"
            collision.write_text("existing", encoding="utf-8")
            folder = root / "figures"
            folder.mkdir()

            with self.assertRaisesRegex(ProjectFileOperationError, "不在当前项目"):
                plan_project_path_move(root, source, Path(directory) / "outside.tex")
            with self.assertRaisesRegex(ProjectFileOperationError, "同名"):
                plan_project_path_move(root, source, collision)
            with self.assertRaisesRegex(ProjectFileOperationError, "项目根目录"):
                plan_project_path_move(root, root, root.parent / "renamed")
            with self.assertRaisesRegex(ProjectFileOperationError, "自己的内部"):
                plan_project_path_move(root, folder, folder / "nested")

    def test_plan_rejects_symlink_and_internal_build_directory(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.tex"
            target.write_text("x", encoding="utf-8")
            link = root / "link.tex"
            link.symlink_to(target)
            internal = root / ".icstex"
            internal.mkdir()
            cache = internal / "cache.tex"
            cache.write_text("x", encoding="utf-8")

            with self.assertRaisesRegex(ProjectFileOperationError, "符号链接"):
                plan_project_path_move(root, link, root / "renamed.tex")
            with self.assertRaisesRegex(ProjectFileOperationError, "内部预览"):
                plan_project_path_move(root, cache, root / "cache.tex")

    def test_reference_scan_blocks_incoming_tex_bib_and_image_references(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            chapters = root / "chapters"
            figures = root / "figures"
            bib = root / "bib"
            chapters.mkdir()
            figures.mkdir()
            bib.mkdir()
            chapter = chapters / "one.tex"
            image = figures / "plot.png"
            references = bib / "references.bib"
            chapter.write_text("Body", encoding="utf-8")
            image.write_bytes(b"png")
            references.write_text("@book{x}", encoding="utf-8")
            main = root / "main.tex"
            main.write_text(
                "\\input{chapters/one}\n"
                "\\includegraphics{figures/plot}\n"
                "\\addbibresource{bib/references.bib}\n",
                encoding="utf-8",
            )

            cases = ((chapter, "input"), (image, "includegraphics"), (references, "addbibresource"))
            for source, command in cases:
                plan = plan_project_path_move(root, source, source.with_name(f"renamed{source.suffix}"))
                blockers = find_move_blockers(plan)
                self.assertEqual(len(blockers), 1)
                self.assertEqual(blockers[0].owner, main.resolve())
                self.assertEqual(blockers[0].command, command)
                self.assertEqual(blockers[0].reason, "其他 LaTeX 文件仍引用该路径")

    def test_reference_scan_uses_unsaved_override_and_ignores_comments(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "plot.png"
            image.write_bytes(b"png")
            main = root / "main.tex"
            main.write_text("% \\includegraphics{plot.png}\n", encoding="utf-8")
            plan = plan_project_path_move(root, image, root / "renamed.png")

            self.assertEqual(find_move_blockers(plan), ())
            blockers = find_move_blockers(
                plan,
                text_overrides={main: "\\includegraphics{plot.png}\n"},
            )

            self.assertEqual(len(blockers), 1)
            self.assertEqual(blockers[0].line, 1)

    def test_reference_scan_includes_style_files_and_named_dynamic_targets(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "plot.png"
            image.write_bytes(b"png")
            style = root / "local.sty"
            style.write_text("\\includegraphics{\\assetdir/plot}\n", encoding="utf-8")
            plan = plan_project_path_move(root, image, root / "renamed.png")

            blockers = find_move_blockers(plan)

            self.assertEqual(len(blockers), 1)
            self.assertEqual(blockers[0].owner, style.resolve())
            self.assertIn("动态", blockers[0].reason)

    def test_directory_internal_references_move_together(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "chapters"
            old.mkdir()
            main = old / "main.tex"
            child = old / "child.tex"
            main.write_text("\\input{child}\n", encoding="utf-8")
            child.write_text("Body", encoding="utf-8")
            plan = plan_project_path_move(root, old, root / "sections")

            self.assertEqual(find_move_blockers(plan), ())
            self.assertEqual(
                remap_moved_path(child, plan),
                (root / "sections" / "child.tex").resolve(),
            )

    def test_cross_directory_move_blocks_changed_relative_reference(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            chapters = root / "chapters"
            archive = root / "archive" / "old"
            shared = root / "shared"
            chapters.mkdir()
            archive.mkdir(parents=True)
            shared.mkdir()
            chapter = chapters / "one.tex"
            shared_file = shared / "note.tex"
            shared_file.write_text("Shared", encoding="utf-8")
            chapter.write_text("\\input{../shared/note}\n", encoding="utf-8")
            plan = plan_project_path_move(root, chapter, archive / chapter.name)

            blockers = find_move_blockers(plan)

            self.assertEqual(len(blockers), 1)
            self.assertEqual(blockers[0].owner, chapter.resolve())
            self.assertIn("相对引用", blockers[0].reason)

    def test_cross_directory_move_checks_magic_root_comment(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            chapters = root / "chapters"
            nested = root / "archive" / "nested"
            chapters.mkdir()
            nested.mkdir(parents=True)
            main = root / "main.tex"
            child = chapters / "child.tex"
            main.write_text("Main", encoding="utf-8")
            child.write_text("% !TEX root = ../main.tex\nChild", encoding="utf-8")
            plan = plan_project_path_move(root, child, nested / child.name)

            blockers = find_move_blockers(plan)

            self.assertEqual(len(blockers), 1)
            self.assertEqual(blockers[0].command, "magic-root")
            self.assertIn("相对引用", blockers[0].reason)

    def test_execute_moves_unreferenced_path_without_overwrite(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "draft.tex"
            source.write_text("Draft", encoding="utf-8")
            destination = rename_destination(source, "notes.tex")
            plan = plan_project_path_move(root, source, destination)

            execute_project_path_move(plan)

            self.assertFalse(source.exists())
            self.assertEqual(destination.read_text(encoding="utf-8"), "Draft")

    def test_rename_destination_requires_one_component(self) -> None:
        with self.assertRaises(ProjectFileOperationError):
            rename_destination(Path("draft.tex"), "../escape.tex")
        with self.assertRaises(ProjectFileOperationError):
            rename_destination(Path("draft.tex"), " ")
