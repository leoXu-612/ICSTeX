"""ICSTeX stdio MCP adapter.

The protocol layer is intentionally thin: all path, permission, CAS, and
execution decisions live in ``app.core.agent_workspace``.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from app.core.agent_workspace import AgentGrants, AgentWorkspace


SERVER_INSTRUCTIONS = """Operate one local ICSTeX project.

Call inspect_project first.  Read before writing and pass the returned SHA-256
back to write_document.  Block mutations require the current block-project
SHA-256 and updates/deletes also require the current Block revision.  Startup
grants, not tool arguments, control write, compile, network, recognition, raw
LaTeX, and export authority.  Recognition results are candidates that require
review.  This server cannot control the GUI or see unsaved GUI buffers; keep the
same project closed or read-only in the GUI while mutating it through MCP.
"""


def create_server(workspace: AgentWorkspace):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised by CLI install guidance
        raise RuntimeError(
            "缺少 MCP SDK；请运行 `python3 -m pip install -e '.[agent]'`。"
        ) from exc

    server = FastMCP("ICSTeX", instructions=SERVER_INSTRUCTIONS)

    @server.tool()
    def inspect_project() -> dict[str, Any]:
        """Inspect root, files, Block state, toolchain, grants, and interaction limits."""

        return workspace.inspect_project()

    @server.tool()
    def read_document(path: str, snapshot_id: str = "") -> dict[str, Any]:
        """Read an allowed project text file or a verified preimage snapshot."""

        return workspace.read_document(path, snapshot_id=snapshot_id)

    @server.tool()
    def write_document(
        path: str,
        text: str,
        expected_sha256: str,
        encoding: str = "",
    ) -> dict[str, Any]:
        """CAS-write a project text file and retain its byte-exact preimage."""

        return workspace.write_document(
            path,
            text,
            expected_sha256=expected_sha256,
            encoding=encoding,
        )

    @server.tool()
    def restore_snapshot(
        path: str,
        snapshot_id: str,
        expected_sha256: str,
    ) -> dict[str, Any]:
        """CAS-restore a verified text or image preimage and retain an undo preimage."""

        return workspace.restore_snapshot(
            path,
            snapshot_id,
            expected_sha256=expected_sha256,
        )

    @server.tool()
    def import_asset(
        input_id: str,
        destination_path: str,
        source_path: str = "",
        expected_sha256: str = "missing",
    ) -> dict[str, Any]:
        """Copy an image from a host-approved input into figures/ or assets/."""

        return workspace.import_asset(
            input_id,
            destination_path,
            source_path=source_path,
            expected_sha256=expected_sha256,
        )

    @server.tool()
    def query_project(
        kind: str,
        path: str = "main.tex",
        query: str = "",
        case_sensitive: bool = False,
        whole_word: bool = False,
        line: int = 1,
        page: int = 1,
        x: float = 0.0,
        y: float = 0.0,
    ) -> dict[str, Any]:
        """Query search, history, diagnostics, counts, references, assets, Blocks, or SyncTeX."""

        return workspace.query_project(
            kind,
            path=path,
            query=query,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
            line=line,
            page=page,
            x=x,
            y=y,
        )

    @server.tool()
    def mutate_blocks(
        operation: str,
        payload: dict[str, Any],
        expected_project_sha256: str,
    ) -> dict[str, Any]:
        """CAS-mutate Blocks, layout, document theme, sources, or generated LaTeX."""

        return workspace.mutate_blocks(
            operation,
            payload,
            expected_project_sha256=expected_project_sha256,
        )

    @server.tool()
    def compile_project(
        action: str = "run",
        root_path: str = "main.tex",
        purpose: str = "preview",
        engine: str = "auto",
        assemble_blocks: bool = False,
        expected_project_sha256: str = "",
    ) -> dict[str, Any]:
        """Run or stop a bounded preview/final compile; never enables shell escape or rc files."""

        return workspace.compile_project(
            action=action,
            root_path=root_path,
            purpose=purpose,
            engine=engine,
            assemble_blocks=assemble_blocks,
            expected_project_sha256=expected_project_sha256,
        )

    @server.tool()
    def recognize_image(kind: str, image_path: str, temperature: float = 0.01) -> dict[str, Any]:
        """Run installed local OCR and return a review-only candidate without writing."""

        return workspace.recognize_image(kind, image_path, temperature=temperature)

    @server.tool()
    def fetch_reference_metadata(raw_text: str) -> dict[str, Any]:
        """Fetch DOI or arXiv BibTeX through ICSTeX's fixed HTTPS allowlist."""

        return workspace.fetch_reference_metadata(raw_text)

    @server.tool()
    def export_artifact(
        kind: str,
        target_path: str,
        root_path: str = "main.tex",
        assemble_blocks: bool = False,
        expected_project_sha256: str = "",
    ) -> dict[str, Any]:
        """Export a fresh final PDF or portable project into the host-approved export root."""

        return workspace.export_artifact(
            kind,
            target_path,
            root_path=root_path,
            assemble_blocks=assemble_blocks,
            expected_project_sha256=expected_project_sha256,
        )

    return server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ICSTeX local stdio MCP server")
    parser.add_argument("--project-root", type=Path, required=True, help="one existing ICSTeX project directory")
    parser.add_argument("--allow-write", action="store_true", help="allow CAS-protected project writes")
    parser.add_argument("--allow-compile", action="store_true", help="allow local LaTeX and SyncTeX execution")
    parser.add_argument("--allow-network", action="store_true", help="allow explicit Crossref/arXiv metadata lookup")
    parser.add_argument("--allow-recognition", action="store_true", help="allow installed local OCR sidecars")
    parser.add_argument(
        "--allow-trusted-raw-latex",
        action="store_true",
        help="allow trusted rawLatex Blocks during explicit Block assembly",
    )
    parser.add_argument("--export-root", type=Path, help="existing directory that may receive new exports")
    parser.add_argument(
        "--allow-input",
        type=Path,
        action="append",
        default=[],
        help="host-approved file/directory usable only by import_asset; repeatable",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.allow_trusted_raw_latex and not args.allow_write:
        parser.error("--allow-trusted-raw-latex requires --allow-write")
    workspace = AgentWorkspace(
        args.project_root,
        grants=AgentGrants(
            allow_write=args.allow_write,
            allow_compile=args.allow_compile,
            allow_network=args.allow_network,
            allow_recognition=args.allow_recognition,
            allow_trusted_raw_latex=args.allow_trusted_raw_latex,
            export_root=args.export_root,
            allowed_inputs=tuple(args.allow_input),
        ),
    )
    create_server(workspace).run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
