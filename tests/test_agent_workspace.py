from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
from unittest import TestCase
from unittest.mock import Mock, patch

from app.core.agent_workspace import (
    AgentGrants,
    AgentWorkspace,
    AgentWorkspaceError,
    CapabilityDenied,
    ConflictError,
    UnsafePathError,
)


MAIN_TEX = """\\documentclass{article}
\\begin{document}
Hello \\label{sec:a} \\ref{sec:a} \\cite{source}
\\end{document}
"""


def _process_cas_write(root: str, digest: str, text: str, barrier: object, results: object) -> None:
    workspace = AgentWorkspace(Path(root), grants=AgentGrants(allow_write=True))
    barrier.wait(timeout=5)  # type: ignore[attr-defined]
    try:
        workspace.write_document("main.tex", text, expected_sha256=digest)
    except ConflictError:
        results.put(("conflict", text))  # type: ignore[attr-defined]
    else:
        results.put(("success", text))  # type: ignore[attr-defined]


class AgentWorkspaceTests(TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name).resolve()
        (self.root / "main.tex").write_text(MAIN_TEX, encoding="utf-8")
        (self.root / "references.bib").write_text("@book{source, title={A}}\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_default_is_read_only_and_compile_network_recognition_are_denied(self) -> None:
        workspace = AgentWorkspace(self.root)
        digest = workspace.read_document("main.tex")["sha256"]

        with self.assertRaises(CapabilityDenied):
            workspace.write_document("main.tex", "changed", expected_sha256=digest)
        with patch("app.core.agent_workspace.CompileManager") as manager, self.assertRaises(CapabilityDenied):
            workspace.compile_project()
        manager.assert_not_called()
        with patch("app.core.agent_workspace.fetch_bib_online") as fetch, self.assertRaises(CapabilityDenied):
            workspace.fetch_reference_metadata("10.1000/example")
        fetch.assert_not_called()
        with patch.object(workspace, "_recognize_formula") as recognize, self.assertRaises(CapabilityDenied):
            workspace.recognize_image("formula", "main.tex")
        recognize.assert_not_called()

    def test_read_rejects_traversal_absolute_backslash_symlink_and_fifo(self) -> None:
        workspace = AgentWorkspace(self.root)
        outside = self.root.parent / "outside-agent-workspace.tex"
        outside.write_text("secret", encoding="utf-8")
        self.addCleanup(outside.unlink, missing_ok=True)
        for value in ("../outside-agent-workspace.tex", str(outside), "..\\outside.tex", "https://example.test/a.tex"):
            with self.subTest(value=value), self.assertRaises(UnsafePathError):
                workspace.read_document(value)

        link = self.root / "linked.tex"
        try:
            link.symlink_to(outside)
        except OSError:
            pass
        else:
            with self.assertRaises(UnsafePathError):
                workspace.read_document("linked.tex")

        if hasattr(os, "mkfifo"):
            fifo = self.root / "pipe.tex"
            os.mkfifo(fifo)
            with self.assertRaises(UnsafePathError):
                workspace.read_document("pipe.tex")

    def test_query_rejects_tex_dependency_outside_project_before_read(self) -> None:
        outside = self.root.parent / "outside-agent-chapter.tex"
        outside.write_text("TOP SECRET", encoding="utf-8")
        self.addCleanup(outside.unlink, missing_ok=True)
        (self.root / "main.tex").write_text(
            "\\documentclass{article}\n\\begin{document}\\input{../outside-agent-chapter}\\end{document}\n",
            encoding="utf-8",
        )
        workspace = AgentWorkspace(self.root)
        with patch.object(workspace, "_read_limited", wraps=workspace._read_limited) as read:
            with self.assertRaises(UnsafePathError):
                workspace.query_project("references")
        self.assertNotIn(outside, [call.args[0] for call in read.call_args_list])

    def test_tex_dependency_parent_segments_are_allowed_when_they_stay_in_project(self) -> None:
        chapters = self.root / "chapters"
        shared = self.root / "shared"
        chapters.mkdir()
        shared.mkdir()
        (self.root / "main.tex").write_text(
            "\\documentclass{article}\\begin{document}\\input{chapters/one}\\end{document}",
            encoding="utf-8",
        )
        (chapters / "one.tex").write_text("\\input{../shared/two}", encoding="utf-8")
        (shared / "two.tex").write_text("inside", encoding="utf-8")

        references = AgentWorkspace(self.root).query_project("references")

        self.assertEqual(references["undefinedReferences"], [])

    def test_magic_root_outside_project_is_rejected_before_read(self) -> None:
        outside = self.root.parent / "outside-agent-root.tex"
        outside.write_text("TOP SECRET", encoding="utf-8")
        self.addCleanup(outside.unlink, missing_ok=True)
        chapter = self.root / "chapter.tex"
        chapter.write_text("% !TEX root = ../outside-agent-root.tex\nchapter\n", encoding="utf-8")
        workspace = AgentWorkspace(self.root)
        with patch.object(workspace, "_read_limited", wraps=workspace._read_limited) as read:
            with self.assertRaises(UnsafePathError):
                workspace.query_project("outline", path="chapter.tex")
        self.assertNotIn(outside, [call.args[0] for call in read.call_args_list])

    def test_cas_write_creates_verified_byte_exact_snapshot(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_write=True))
        before = workspace.read_document("main.tex")
        result = workspace.write_document(
            "main.tex",
            MAIN_TEX + "% changed\n",
            expected_sha256=before["sha256"],
        )

        self.assertIsNotNone(result["snapshotId"])
        restored = workspace.read_document("main.tex", snapshot_id=result["snapshotId"])
        self.assertEqual(restored["text"], MAIN_TEX)
        self.assertEqual(restored["sha256"], before["sha256"])
        history = workspace.query_project("history", path="main.tex")
        self.assertEqual(history["snapshots"][0]["id"], result["snapshotId"])

        restored_result = workspace.restore_snapshot(
            "main.tex",
            result["snapshotId"],
            expected_sha256=result["sha256"],
        )
        self.assertEqual((self.root / "main.tex").read_text(encoding="utf-8"), MAIN_TEX)
        self.assertEqual(restored_result["sha256"], before["sha256"])
        self.assertIsNotNone(restored_result["undoSnapshotId"])

    def test_cas_conflict_has_zero_write_and_zero_snapshot(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_write=True))
        before = (self.root / "main.tex").read_bytes()

        with self.assertRaises(ConflictError):
            workspace.write_document("main.tex", "changed", expected_sha256="0" * 64)

        self.assertEqual((self.root / "main.tex").read_bytes(), before)
        entries = self.root / ".icstex" / "agent-history" / "entries"
        self.assertFalse(entries.exists())

    def test_encoding_failure_has_zero_write_and_zero_snapshot(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_write=True))
        before = workspace.read_document("main.tex")
        with self.assertRaises(AgentWorkspaceError):
            workspace.write_document(
                "main.tex",
                "中文",
                expected_sha256=before["sha256"],
                encoding="ascii",
            )
        self.assertEqual((self.root / "main.tex").read_text(encoding="utf-8"), MAIN_TEX)
        self.assertFalse((self.root / ".icstex" / "agent-history" / "entries").exists())

    def test_two_concurrent_writers_with_same_hash_only_one_succeeds(self) -> None:
        workspace_a = AgentWorkspace(self.root, grants=AgentGrants(allow_write=True))
        workspace_b = AgentWorkspace(self.root, grants=AgentGrants(allow_write=True))
        digest = workspace_a.read_document("main.tex")["sha256"]
        barrier = threading.Barrier(2)
        successes: list[str] = []
        conflicts: list[str] = []

        def write(workspace: AgentWorkspace, text: str) -> None:
            barrier.wait()
            try:
                workspace.write_document("main.tex", text, expected_sha256=digest)
                successes.append(text)
            except ConflictError:
                conflicts.append(text)

        threads = [
            threading.Thread(target=write, args=(workspace_a, "first")),
            threading.Thread(target=write, args=(workspace_b, "second")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual((self.root / "main.tex").read_text(encoding="utf-8"), successes[0])

    def test_two_process_writers_with_same_hash_only_one_succeeds(self) -> None:
        digest = AgentWorkspace(self.root).read_document("main.tex")["sha256"]
        context = multiprocessing.get_context("spawn")
        barrier = context.Barrier(2)
        results = context.Queue()
        processes = [
            context.Process(
                target=_process_cas_write,
                args=(str(self.root), digest, text, barrier, results),
            )
            for text in ("first process", "second process")
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join(2)
                self.fail("cross-process CAS writer did not finish")
            self.assertEqual(process.exitcode, 0)

        outcomes = [results.get(timeout=2), results.get(timeout=2)]
        self.assertEqual(sorted(outcome for outcome, _text in outcomes), ["conflict", "success"])
        successful_text = next(text for outcome, text in outcomes if outcome == "success")
        self.assertEqual((self.root / "main.tex").read_text(encoding="utf-8"), successful_text)

    def test_block_crud_requires_project_etag_and_block_revision(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_write=True))
        etag = workspace.block_project_sha256()
        created = workspace.mutate_blocks(
            "create",
            {
                "type": "text",
                "alias": "intro",
                "semantic": {"role": "text"},
                "content": {"format": "plain", "text": "hello"},
                "references": [],
                "provenance": {"kind": "created"},
            },
            expected_project_sha256=etag,
        )
        block = created["block"]
        with self.assertRaises(ConflictError):
            workspace.mutate_blocks(
                "update",
                {"blockId": block["id"], "expectedRevision": 99, "patch": {"alias": "changed"}},
                expected_project_sha256=created["blockProjectSha256"],
            )
        updated = workspace.mutate_blocks(
            "update",
            {"blockId": block["id"], "expectedRevision": 1, "patch": {"alias": "changed"}},
            expected_project_sha256=created["blockProjectSha256"],
        )
        self.assertEqual(updated["block"]["alias"], "changed")
        self.assertEqual(updated["block"]["revision"], 2)

    def test_block_state_rejects_symlinked_metadata(self) -> None:
        outside = self.root.parent / "outside-agent-blocks.json"
        outside.write_text('{"format":"icstex-blocks","schemaVersion":"1.0.0","blocks":[]}', encoding="utf-8")
        self.addCleanup(outside.unlink, missing_ok=True)
        metadata = self.root / ".icstex"
        metadata.mkdir()
        try:
            (metadata / "blocks.json").symlink_to(outside)
        except OSError:
            self.skipTest("symlink unavailable")
        with self.assertRaises(UnsafePathError):
            AgentWorkspace(self.root).query_project("blocks")

    def test_block_state_rejects_invalid_layout_instead_of_silent_fallback(self) -> None:
        metadata = self.root / ".icstex"
        metadata.mkdir()
        (metadata / "layouts.json").write_text(
            json.dumps({"layouts": [{"schemaVersion": "1.0.0", "id": "bad", "kind": "video", "children": []}]}),
            encoding="utf-8",
        )
        with self.assertRaises(AgentWorkspaceError):
            AgentWorkspace(self.root).query_project("blocks")

    def test_layout_rejects_missing_block_reference_without_write(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_write=True))
        etag = workspace.block_project_sha256()
        layout = {
            "schemaVersion": "1.0.0",
            "id": "lyt_root",
            "kind": "row",
            "children": [
                {"instanceId": "ins_missing", "kind": "block", "blockId": "blk_missing", "weight": 1.0}
            ],
        }
        with self.assertRaises(AgentWorkspaceError):
            workspace.mutate_blocks(
                "set-layout",
                {"layout": layout},
                expected_project_sha256=etag,
            )
        self.assertFalse((self.root / ".icstex" / "layouts.json").exists())

    def test_block_assembly_blocks_trusted_raw_latex_without_host_grant(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_write=True))
        created = workspace.mutate_blocks(
            "create",
            {
                "type": "rawLatex",
                "alias": "raw",
                "semantic": {"role": "text"},
                "content": {"latex": "\\input{/tmp/secret}", "trusted": True},
                "references": [],
                "provenance": {"kind": "created"},
            },
            expected_project_sha256=workspace.block_project_sha256(),
        )
        workspace.mutate_blocks(
            "assemble",
            {},
            expected_project_sha256=created["blockProjectSha256"],
        )
        block_file = next((self.root / "blocks").glob("*.tex"))
        rendered = block_file.read_text(encoding="utf-8")
        self.assertIn("raw-latex blocked", rendered)
        self.assertNotIn("/tmp/secret", rendered)

    def test_assemble_rejects_non_block_project_to_protect_main_tex(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_write=True))
        before = (self.root / "main.tex").read_bytes()
        with self.assertRaises(AgentWorkspaceError):
            workspace.mutate_blocks(
                "assemble",
                {},
                expected_project_sha256=workspace.block_project_sha256(),
            )
        self.assertEqual((self.root / "main.tex").read_bytes(), before)

    def test_block_assembly_failure_rolls_back_all_generated_files(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_write=True))
        created = workspace.mutate_blocks(
            "create",
            {
                "type": "text",
                "alias": "intro",
                "semantic": {"role": "text"},
                "content": {"format": "plain", "text": "hello"},
                "references": [],
                "provenance": {"kind": "created"},
            },
            expected_project_sha256=workspace.block_project_sha256(),
        )
        original_main = (self.root / "main.tex").read_bytes()
        real_write = workspace._atomic_write_bytes
        calls = 0

        def fail_second(path: Path, payload: bytes) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected failure")
            real_write(path, payload)

        with patch.object(workspace, "_atomic_write_bytes", side_effect=fail_second):
            with self.assertRaises(OSError):
                workspace.mutate_blocks(
                    "assemble",
                    {},
                    expected_project_sha256=created["blockProjectSha256"],
                )
        self.assertEqual((self.root / "main.tex").read_bytes(), original_main)
        self.assertEqual(list((self.root / "blocks").glob("*.tex")), [])
        entries = self.root / ".icstex" / "agent-history" / "entries"
        self.assertEqual(list(entries.glob("*.json")) if entries.exists() else [], [])

    def test_compile_rejects_symlink_before_process_launch(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_compile=True))
        outside = self.root.parent / "outside-agent-image.png"
        outside.write_bytes(b"png")
        self.addCleanup(outside.unlink, missing_ok=True)
        try:
            (self.root / "image.png").symlink_to(outside)
        except OSError:
            self.skipTest("symlink unavailable")
        with patch("app.core.agent_workspace.CompileManager") as manager, self.assertRaises(UnsafePathError):
            workspace.compile_project()
        manager.assert_not_called()

    def test_compile_enables_restricted_tex_io(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_compile=True))
        result = Mock()
        result.ok = True
        with patch("app.core.agent_workspace.CompileManager") as manager_type:
            manager_type.return_value.compile_now.return_value = result
            with patch.object(workspace, "_compile_result", return_value={"ok": True}):
                self.assertTrue(workspace.compile_project()["ok"])
        self.assertTrue(manager_type.call_args.kwargs["restricted_io"])

    def test_different_project_roots_can_compile_concurrently(self) -> None:
        with TemporaryDirectory() as other_directory:
            other_root = Path(other_directory).resolve()
            (other_root / "main.tex").write_text(MAIN_TEX, encoding="utf-8")
            workspaces = [
                AgentWorkspace(self.root, grants=AgentGrants(allow_compile=True)),
                AgentWorkspace(other_root, grants=AgentGrants(allow_compile=True)),
            ]
            barrier = threading.Barrier(2)
            state_lock = threading.Lock()
            active = 0
            maximum = 0
            errors: list[BaseException] = []

            def compile_now(*_args: object, **_kwargs: object) -> object:
                nonlocal active, maximum
                with state_lock:
                    active += 1
                    maximum = max(maximum, active)
                barrier.wait(timeout=2)
                time.sleep(0.02)
                with state_lock:
                    active -= 1
                return object()

            def manager_factory(*_args: object, **_kwargs: object) -> Mock:
                manager = Mock()
                manager.compile_now.side_effect = compile_now
                manager.retire.return_value = True
                return manager

            def run(workspace: AgentWorkspace) -> None:
                try:
                    workspace.compile_project()
                except BaseException as exc:  # noqa: BLE001 - collected for the parent assertion
                    errors.append(exc)

            with patch("app.core.agent_workspace.CompileManager", side_effect=manager_factory):
                with patch.object(workspaces[0], "_compile_result", return_value={"ok": True}), patch.object(
                    workspaces[1], "_compile_result", return_value={"ok": True}
                ):
                    threads = [threading.Thread(target=run, args=(workspace,)) for workspace in workspaces]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join(4)

            self.assertEqual(errors, [])
            self.assertEqual(maximum, 2)

    def test_same_project_compile_requests_are_serialized(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_compile=True))
        start = threading.Barrier(3)
        state_lock = threading.Lock()
        active = 0
        maximum = 0
        completed = 0
        errors: list[BaseException] = []

        def compile_now(*_args: object, **_kwargs: object) -> object:
            nonlocal active, maximum, completed
            with state_lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.04)
            with state_lock:
                active -= 1
                completed += 1
            return object()

        def manager_factory(*_args: object, **_kwargs: object) -> Mock:
            manager = Mock()
            manager.compile_now.side_effect = compile_now
            manager.retire.return_value = True
            return manager

        def run() -> None:
            start.wait()
            try:
                workspace.compile_project()
            except BaseException as exc:  # noqa: BLE001 - collected for the parent assertion
                errors.append(exc)

        with patch("app.core.agent_workspace.CompileManager", side_effect=manager_factory), patch.object(
            workspace, "_compile_result", return_value={"ok": True}
        ):
            threads = [threading.Thread(target=run) for _ in range(2)]
            for thread in threads:
                thread.start()
            start.wait()
            for thread in threads:
                thread.join(4)

        self.assertEqual(errors, [])
        self.assertEqual(completed, 2)
        self.assertEqual(maximum, 1)

    def test_stop_cancels_waiting_compile_request(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_compile=True))
        active_entered = threading.Event()
        release_active = threading.Event()
        errors: list[BaseException] = []
        results: list[dict] = []
        managers: list[Mock] = []

        def manager_factory(*_args: object, **_kwargs: object) -> Mock:
            manager = Mock()
            if not managers:
                manager.compile_now.side_effect = lambda *_a, **_k: (
                    active_entered.set(),
                    release_active.wait(3),
                    object(),
                )[-1]
                manager.retire.side_effect = lambda timeout=1.5: (release_active.set(), True)[-1]
            else:
                manager.compile_now.return_value = object()
                manager.retire.return_value = True
            managers.append(manager)
            return manager

        def run() -> None:
            try:
                results.append(workspace.compile_project())
            except BaseException as exc:  # noqa: BLE001 - cancellation is the assertion target
                errors.append(exc)

        with patch("app.core.agent_workspace.CompileManager", side_effect=manager_factory), patch.object(
            workspace, "_compile_result", return_value={"ok": True}
        ):
            first = threading.Thread(target=run)
            second = threading.Thread(target=run)
            first.start()
            self.assertTrue(active_entered.wait(1))
            second.start()
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                with workspace._compile_lock:
                    if workspace._compile_requests == 2:
                        break
                time.sleep(0.005)
            else:
                self.fail("second compile request was not registered")

            stopped = workspace.compile_project(action="stop")
            first.join(3)
            second.join(3)

        self.assertTrue(stopped["stopped"])
        self.assertEqual(results, [{"ok": True}])
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], AgentWorkspaceError)
        self.assertIn("stop 取消", str(errors[0]))
        managers[0].retire.assert_called_once()

    def test_compile_deadline_includes_validation_time(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_compile=True))

        def slow_validation(_root: Path) -> None:
            time.sleep(0.03)

        with patch.object(workspace, "_validate_tex_closure", side_effect=slow_validation), patch(
            "app.core.agent_workspace.CompileManager"
        ) as manager:
            with self.assertRaisesRegex(AgentWorkspaceError, "等待超时"):
                workspace.compile_project(deadline_monotonic=time.monotonic() + 0.01)
        manager.assert_not_called()

    def test_recognition_returns_review_only_sanitized_candidate_and_never_writes(self) -> None:
        image = self.root / "formula.png"
        image.write_bytes(b"image")
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_recognition=True))
        before = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        with patch.object(workspace, "_recognize_formula", return_value={"latex": r"\\input{/etc/passwd}", "elapsed_ms": 4}):
            result = workspace.recognize_image("formula", "formula.png")
        after = {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

        self.assertTrue(result["reviewRequired"])
        self.assertFalse(result["safe"])
        self.assertIn("forbidden_command:input", result["errors"])
        self.assertEqual(after, before)

    def test_external_asset_import_requires_named_host_input_and_project_asset_destination(self) -> None:
        with TemporaryDirectory() as external:
            source = Path(external).resolve() / "plot.png"
            source.write_bytes(b"plot")
            workspace = AgentWorkspace(
                self.root,
                grants=AgentGrants(allow_write=True, allowed_inputs=(Path(external),)),
            )
            result = workspace.import_asset("input_1", "figures/plot.png", source_path="plot.png")
            self.assertEqual((self.root / "figures" / "plot.png").read_bytes(), b"plot")
            self.assertEqual(result["sha256"], hashlib.sha256(b"plot").hexdigest())
            with self.assertRaises(UnsafePathError):
                workspace.import_asset("input_1", "notes/plot.png", source_path="plot.png")

    def test_binary_asset_snapshot_can_be_restored(self) -> None:
        with TemporaryDirectory() as external:
            source = Path(external).resolve() / "plot.png"
            source.write_bytes(b"new")
            destination = self.root / "figures" / "plot.png"
            destination.parent.mkdir()
            destination.write_bytes(b"old")
            old_hash = hashlib.sha256(b"old").hexdigest()
            workspace = AgentWorkspace(
                self.root,
                grants=AgentGrants(allow_write=True, allowed_inputs=(source,)),
            )
            imported = workspace.import_asset(
                "input_1",
                "figures/plot.png",
                expected_sha256=old_hash,
            )
            restored = workspace.restore_snapshot(
                "figures/plot.png",
                imported["snapshotId"],
                expected_sha256=imported["sha256"],
            )
        self.assertEqual(destination.read_bytes(), b"old")
        self.assertEqual(restored["sha256"], old_hash)

    def test_invalid_block_state_snapshot_restore_rolls_back(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_write=True))
        created = workspace.mutate_blocks(
            "create",
            {
                "type": "text",
                "alias": "intro",
                "semantic": {"role": "text"},
                "content": {"format": "plain", "text": "hello"},
                "references": [],
                "provenance": {"kind": "created"},
            },
            expected_project_sha256=workspace.block_project_sha256(),
        )
        blocks = self.root / ".icstex" / "blocks.json"
        valid = blocks.read_bytes()
        bad_object = b"not json"
        bad_hash = hashlib.sha256(bad_object).hexdigest()
        history = self.root / ".icstex" / "agent-history"
        (history / "objects").mkdir(parents=True)
        (history / "entries").mkdir(parents=True)
        snapshot_id = "f" * 32
        (history / "objects" / f"{bad_hash}.bin").write_bytes(bad_object)
        (history / "entries" / f"{snapshot_id}.json").write_text(
            json.dumps(
                {
                    "id": snapshot_id,
                    "relativePath": ".icstex/blocks.json",
                    "sha256": bad_hash,
                    "encoding": "utf-8",
                    "size": len(bad_object),
                    "createdAt": "2026-08-13T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(AgentWorkspaceError):
            workspace.restore_snapshot(
                ".icstex/blocks.json",
                snapshot_id,
                expected_sha256=hashlib.sha256(valid).hexdigest(),
            )
        self.assertEqual(blocks.read_bytes(), valid)
        self.assertEqual(workspace.block_project_sha256(), created["blockProjectSha256"])

    def test_query_search_references_diagnostics_and_blocks_are_project_scoped(self) -> None:
        workspace = AgentWorkspace(self.root)
        self.assertEqual(workspace.query_project("search", query="Hello")["results"][0]["file"], "main.tex")
        references = workspace.query_project("references")
        self.assertEqual(references["undefinedReferences"], [])
        self.assertEqual(references["undefinedCitations"], [])
        self.assertIn("diagnostics", workspace.query_project("diagnostics"))
        self.assertIn("blockProjectSha256", workspace.query_project("blocks"))

    def test_read_only_word_count_does_not_launch_texcount(self) -> None:
        workspace = AgentWorkspace(self.root)
        with patch("app.core.word_count.subprocess.run") as run:
            result = workspace.query_project("word-count")
        run.assert_not_called()
        self.assertEqual(result["result"]["source"], "fallback")

    def test_read_only_environment_does_not_run_version_commands(self) -> None:
        workspace = AgentWorkspace(self.root)
        with patch("app.core.environment_doctor.subprocess.run") as run:
            result = workspace.query_project("environment")
        run.assert_not_called()
        self.assertIn("tools", result)

    def test_network_grant_uses_existing_allowlisted_fetcher(self) -> None:
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_network=True))
        expected = Mock(key="k", bibtex="@misc{k}", source="DOI")
        with patch("app.core.agent_workspace.fetch_bib_online", return_value=expected) as fetch:
            result = workspace.fetch_reference_metadata("10.1000/example")
        fetch.assert_called_once_with("10.1000/example")
        self.assertTrue(result["found"])

    def test_recognition_rejects_nonfinite_temperature_before_worker(self) -> None:
        image = self.root / "formula.png"
        image.write_bytes(b"image")
        workspace = AgentWorkspace(self.root, grants=AgentGrants(allow_recognition=True))
        with patch.object(workspace, "_recognize_formula") as recognize, self.assertRaises(AgentWorkspaceError):
            workspace.recognize_image("formula", "formula.png", temperature=float("nan"))
        recognize.assert_not_called()


class AgentWorkspaceExportTests(TestCase):
    def test_export_target_must_be_new_and_within_host_root(self) -> None:
        with TemporaryDirectory() as project_dir, TemporaryDirectory() as export_dir:
            project = Path(project_dir).resolve()
            export = Path(export_dir).resolve()
            (project / "main.tex").write_text(MAIN_TEX, encoding="utf-8")
            workspace = AgentWorkspace(project, grants=AgentGrants(export_root=export))
            existing = export / "existing"
            existing.mkdir()
            with self.assertRaises(ConflictError):
                workspace.export_artifact("package", "existing")
            with self.assertRaises(UnsafePathError):
                workspace.export_artifact("package", "../outside")

    def test_export_root_cannot_overlap_project(self) -> None:
        with TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            (project / "main.tex").write_text(MAIN_TEX, encoding="utf-8")
            export = project / "exports"
            export.mkdir()
            workspace = AgentWorkspace(project, grants=AgentGrants(export_root=export))
            with self.assertRaises(UnsafePathError):
                workspace.export_artifact("package", "package")

    def test_package_export_can_reenter_project_lock_for_block_assembly(self) -> None:
        with TemporaryDirectory() as project_dir, TemporaryDirectory() as export_dir:
            project = Path(project_dir).resolve()
            export = Path(export_dir).resolve()
            (project / "main.tex").write_text(MAIN_TEX, encoding="utf-8")
            workspace = AgentWorkspace(
                project,
                grants=AgentGrants(allow_write=True, export_root=export),
            )
            created = workspace.mutate_blocks(
                "create",
                {
                    "type": "text",
                    "alias": "intro",
                    "semantic": {"role": "text"},
                    "content": {"format": "plain", "text": "hello"},
                    "references": [],
                    "provenance": {"kind": "created"},
                },
                expected_project_sha256=workspace.block_project_sha256(),
            )

            result = workspace.export_artifact(
                "package",
                "assembled",
                assemble_blocks=True,
                expected_project_sha256=created["blockProjectSha256"],
            )

            self.assertEqual(result["kind"], "package")
            self.assertTrue((export / "assembled" / "main.tex").is_file())
