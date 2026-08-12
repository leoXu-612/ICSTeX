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
                    names = {tool.name for tool in tools.tools}
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
