from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import time
from unittest import TestCase, skipUnless
from unittest.mock import Mock, patch

try:
    from mcp import Client, ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:  # Optional dependency: base desktop tests remain runnable.
    Client = ClientSession = StdioServerParameters = stdio_client = None  # type: ignore[assignment]

from app import __version__
from app.core.agent_workspace import AgentGrants, AgentWorkspace
from app.mcp_server import create_server


@skipUnless(ClientSession is not None, "optional MCP SDK is not installed")
class MCPServerProtocolTests(TestCase):
    def test_real_stdio_handshake_lists_tools_and_calls_inspect(self) -> None:
        async def exercise(project: Path) -> None:
            assert StdioServerParameters is not None and stdio_client is not None and ClientSession is not None
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "app.mcp_server", "--project-root", str(project)],
                cwd=str(Path(__file__).resolve().parents[1]),
            )
            async with stdio_client(parameters) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    initialized = await session.initialize()
                    self.assertEqual(initialized.server_info.version, __version__)
                    tools = await session.list_tools()
                    by_name = {tool.name: tool for tool in tools.tools}
                    names = set(by_name)
                    self.assertEqual(
                        names,
                        {
                            "inspect_project",
                            "read_document",
                            "write_document",
                            "restore_snapshot",
                            "import_asset",
                            "query_project",
                            "mutate_blocks",
                            "compile_project",
                            "recognize_image",
                            "fetch_reference_metadata",
                            "export_artifact",
                        },
                    )
                    for name in ("inspect_project", "read_document", "query_project", "recognize_image"):
                        annotations = by_name[name].annotations
                        self.assertIsNotNone(annotations)
                        self.assertTrue(annotations.read_only_hint)
                        self.assertFalse(annotations.open_world_hint)
                    for name in ("write_document", "restore_snapshot", "import_asset", "mutate_blocks", "compile_project"):
                        annotations = by_name[name].annotations
                        self.assertIsNotNone(annotations)
                        self.assertFalse(annotations.read_only_hint)
                        self.assertTrue(annotations.destructive_hint)
                    self.assertTrue(by_name["fetch_reference_metadata"].annotations.open_world_hint)
                    self.assertFalse(by_name["export_artifact"].annotations.destructive_hint)

                    enum_contracts = {
                        ("query_project", "kind"): [
                            "search", "history", "environment", "assets", "blocks", "outline",
                            "word-count", "references", "diagnostics", "synctex-source-to-pdf",
                            "synctex-pdf-to-source",
                        ],
                        ("mutate_blocks", "operation"): [
                            "create", "update", "delete", "set-layout", "set-theme", "set-sources", "assemble",
                        ],
                        ("compile_project", "action"): ["run", "stop"],
                        ("compile_project", "purpose"): ["preview", "final"],
                        ("compile_project", "engine"): ["auto", "pdflatex", "xelatex", "lualatex"],
                        ("recognize_image", "kind"): ["formula", "text"],
                        ("export_artifact", "kind"): ["pdf", "package"],
                    }
                    for (tool_name, argument), expected in enum_contracts.items():
                        properties = by_name[tool_name].input_schema["properties"]
                        self.assertEqual(properties[argument]["enum"], expected)
                    response = await session.call_tool("inspect_project", {})
                    self.assertFalse(response.is_error)
                    self.assertEqual(response.structured_content["rootFile"], "main.tex")
                    self.assertFalse(response.structured_content["grants"]["write"])
                    document = await session.call_tool("read_document", {"path": "main.tex"})
                    denied = await session.call_tool(
                        "write_document",
                        {
                            "path": "main.tex",
                            "text": "changed",
                            "expected_sha256": document.structured_content["sha256"],
                        },
                    )
                    self.assertTrue(denied.is_error)
                    self.assertIn("未授予 write 能力", denied.content[0].text)

        with TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            (project / "main.tex").write_text(
                "\\documentclass{article}\\begin{document}x\\end{document}",
                encoding="utf-8",
            )
            asyncio.run(exercise(project))

    def test_real_stdio_legacy_client_lists_and_calls_tools(self) -> None:
        async def exercise(project: Path) -> None:
            assert Client is not None and StdioServerParameters is not None
            parameters = StdioServerParameters(
                command=sys.executable,
                args=["-m", "app.mcp_server", "--project-root", str(project)],
                cwd=str(Path(__file__).resolve().parents[1]),
            )
            async with Client(parameters, mode="legacy") as client:
                tools = await client.list_tools()
                self.assertEqual(len(tools.tools), 11)
                response = await client.call_tool("inspect_project", {})
                self.assertFalse(response.is_error)
                self.assertEqual(response.structured_content["rootFile"], "main.tex")

        with TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            (project / "main.tex").write_text(
                "\\documentclass{article}\\begin{document}x\\end{document}",
                encoding="utf-8",
            )
            asyncio.run(exercise(project))

    def test_legacy_client_runs_sync_read_tools_concurrently(self) -> None:
        async def exercise(workspace: AgentWorkspace) -> tuple[dict, dict, float]:
            assert Client is not None
            async with Client(create_server(workspace), mode="legacy") as client:
                started = time.perf_counter()
                first, second = await asyncio.gather(
                    client.call_tool("inspect_project", {}),
                    client.call_tool("inspect_project", {}),
                )
                return first.structured_content, second.structured_content, time.perf_counter() - started

        with TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            (project / "main.tex").write_text(
                "\\documentclass{article}\\begin{document}x\\end{document}",
                encoding="utf-8",
            )
            workspace = AgentWorkspace(project)
            barrier = threading.Barrier(2)

            def overlapping_inspect() -> dict:
                barrier.wait(timeout=2)
                time.sleep(0.05)
                return {"threadId": threading.get_ident()}

            workspace.inspect_project = overlapping_inspect  # type: ignore[method-assign]
            first, second, elapsed = asyncio.run(exercise(workspace))

        self.assertNotEqual(first["threadId"], second["threadId"])
        self.assertLess(elapsed, 1.0)

    def test_stop_bypasses_active_compile_and_cancels_queued_call(self) -> None:
        async def exercise(workspace: AgentWorkspace, active_entered: threading.Event):
            assert Client is not None
            async with Client(create_server(workspace), mode="legacy") as client:
                first_task = asyncio.create_task(client.call_tool("compile_project", {}))
                self.assertTrue(await asyncio.to_thread(active_entered.wait, 1))
                second_task = asyncio.create_task(client.call_tool("compile_project", {}))
                await asyncio.to_thread(self._wait_for_compile_requests, workspace, 2)
                stopped = await client.call_tool("compile_project", {"action": "stop"})
                first, second = await asyncio.gather(first_task, second_task)
                return first, second, stopped

        with TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            (project / "main.tex").write_text(
                "\\documentclass{article}\\begin{document}x\\end{document}",
                encoding="utf-8",
            )
            workspace = AgentWorkspace(project, grants=AgentGrants(allow_compile=True))
            active_entered = threading.Event()
            release_active = threading.Event()
            manager = Mock()
            manager.compile_now.side_effect = lambda *_a, **_k: (
                active_entered.set(),
                release_active.wait(3),
                object(),
            )[-1]
            manager.retire.side_effect = lambda timeout=1.5: (release_active.set(), True)[-1]

            with patch("app.core.agent_workspace.CompileManager", return_value=manager), patch.object(
                workspace, "_compile_result", return_value={"ok": True}
            ):
                first, second, stopped = asyncio.run(exercise(workspace, active_entered))

        self.assertFalse(first.is_error)
        self.assertTrue(second.is_error)
        self.assertIn("stop 取消", second.content[0].text)
        self.assertFalse(stopped.is_error)
        self.assertTrue(stopped.structured_content["stopped"])
        manager.compile_now.assert_called_once()
        manager.retire.assert_called_once()

    def _wait_for_compile_requests(self, workspace: AgentWorkspace, expected: int) -> None:
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            with workspace._compile_lock:
                if workspace._compile_requests >= expected:
                    return
            time.sleep(0.005)
        self.fail(f"expected {expected} registered compile requests")
