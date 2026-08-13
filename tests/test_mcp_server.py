from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:  # Optional dependency: base desktop tests remain runnable.
    ClientSession = StdioServerParameters = stdio_client = None  # type: ignore[assignment]


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
                    await session.initialize()
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
                        self.assertTrue(annotations.readOnlyHint)
                        self.assertFalse(annotations.openWorldHint)
                    for name in ("write_document", "restore_snapshot", "import_asset", "mutate_blocks", "compile_project"):
                        annotations = by_name[name].annotations
                        self.assertIsNotNone(annotations)
                        self.assertFalse(annotations.readOnlyHint)
                        self.assertTrue(annotations.destructiveHint)
                    self.assertTrue(by_name["fetch_reference_metadata"].annotations.openWorldHint)
                    self.assertFalse(by_name["export_artifact"].annotations.destructiveHint)

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
                        properties = by_name[tool_name].inputSchema["properties"]
                        self.assertEqual(properties[argument]["enum"], expected)
                    response = await session.call_tool("inspect_project", {})
                    self.assertFalse(response.isError)
                    self.assertEqual(response.structuredContent["rootFile"], "main.tex")
                    self.assertFalse(response.structuredContent["grants"]["write"])

        with TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            (project / "main.tex").write_text(
                "\\documentclass{article}\\begin{document}x\\end{document}",
                encoding="utf-8",
            )
            asyncio.run(exercise(project))
