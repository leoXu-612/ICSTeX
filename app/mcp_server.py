"""ICSTeX stdio MCP adapter.

The protocol layer is intentionally thin: all path, permission, CAS, and
execution decisions live in ``app.core.agent_workspace``.
"""
from __future__ import annotations

import argparse
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Literal, ParamSpec, TypeVar

from app import __version__
from app.core.agent_concurrency import AgentConcurrencyError, WorkspaceConcurrency
from app.core.agent_workspace import AgentGrants, AgentWorkspace, AgentWorkspaceError
from app.core.compiler import FINAL_TIMEOUT_SECONDS, PREVIEW_TIMEOUT_SECONDS


QueryKind = Literal[
    "search",
    "history",
    "environment",
    "assets",
    "blocks",
    "outline",
    "word-count",
    "references",
    "diagnostics",
    "synctex-source-to-pdf",
    "synctex-pdf-to-source",
]
BlockOperation = Literal["create", "update", "delete", "set-layout", "set-theme", "set-sources", "assemble"]
CompileAction = Literal["run", "stop"]
CompilePurpose = Literal["preview", "final"]
CompileEngine = Literal["auto", "pdflatex", "xelatex", "lualatex"]
RecognitionKind = Literal["formula", "text"]
ExportKind = Literal["pdf", "package"]
P = ParamSpec("P")
R = TypeVar("R")


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
        from mcp.server.mcpserver.exceptions import ToolError
        from mcp.server.mcpserver import MCPServer
        from mcp.types import ToolAnnotations
    except ImportError as exc:  # pragma: no cover - exercised by CLI install guidance
        raise RuntimeError(
            "缺少 MCP SDK；请运行 `python3 -m pip install -e '.[agent]'`。"
        ) from exc

    server = MCPServer("ICSTeX", instructions=SERVER_INSTRUCTIONS, version=__version__)
    concurrency = WorkspaceConcurrency()
    read_only = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
    mutating = ToolAnnotations(
        read_only_hint=False,
        destructive_hint=True,
        idempotent_hint=False,
        open_world_hint=False,
    )
    additive = ToolAnnotations(
        read_only_hint=False,
        destructive_hint=False,
        idempotent_hint=False,
        open_world_hint=False,
    )
    network = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=True)

    def anticipated_errors(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def call(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return function(*args, **kwargs)
            except (AgentWorkspaceError, AgentConcurrencyError) as exc:
                raise ToolError(str(exc)) from exc

        return call

    @server.tool(annotations=read_only)
    @anticipated_errors
    def inspect_project() -> dict[str, Any]:
        """Inspect root, files, Block state, toolchain, grants, and interaction limits."""

        with concurrency.read():
            return workspace.inspect_project()

    @server.tool(annotations=read_only)
    @anticipated_errors
    def read_document(path: str, snapshot_id: str = "") -> dict[str, Any]:
        """Read an allowed project text file or a verified preimage snapshot."""

        with concurrency.read():
            return workspace.read_document(path, snapshot_id=snapshot_id)

    @server.tool(annotations=mutating)
    @anticipated_errors
    def write_document(
        path: str,
        text: str,
        expected_sha256: str,
        encoding: str = "",
    ) -> dict[str, Any]:
        """CAS-write a project text file and retain its byte-exact preimage."""

        with concurrency.exclusive():
            return workspace.write_document(
                path,
                text,
                expected_sha256=expected_sha256,
                encoding=encoding,
            )

    @server.tool(annotations=mutating)
    @anticipated_errors
    def restore_snapshot(
        path: str,
        snapshot_id: str,
        expected_sha256: str,
    ) -> dict[str, Any]:
        """CAS-restore a verified text or image preimage and retain an undo preimage."""

        with concurrency.exclusive():
            return workspace.restore_snapshot(
                path,
                snapshot_id,
                expected_sha256=expected_sha256,
            )

    @server.tool(annotations=mutating)
    @anticipated_errors
    def import_asset(
        input_id: str,
        destination_path: str,
        source_path: str = "",
        expected_sha256: str = "missing",
    ) -> dict[str, Any]:
        """Copy an image from a host-approved input into figures/ or assets/."""

        with concurrency.exclusive():
            return workspace.import_asset(
                input_id,
                destination_path,
                source_path=source_path,
                expected_sha256=expected_sha256,
            )

    @server.tool(annotations=read_only)
    @anticipated_errors
    def query_project(
        kind: QueryKind,
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

        with concurrency.read():
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

    @server.tool(annotations=mutating)
    @anticipated_errors
    def mutate_blocks(
        operation: BlockOperation,
        payload: dict[str, Any],
        expected_project_sha256: str,
    ) -> dict[str, Any]:
        """CAS-mutate Blocks, layout, document theme, sources, or generated LaTeX."""

        with concurrency.exclusive():
            return workspace.mutate_blocks(
                operation,
                payload,
                expected_project_sha256=expected_project_sha256,
            )

    @server.tool(annotations=mutating)
    @anticipated_errors
    def compile_project(
        action: CompileAction = "run",
        root_path: str = "main.tex",
        purpose: CompilePurpose = "preview",
        engine: CompileEngine = "auto",
        assemble_blocks: bool = False,
        expected_project_sha256: str = "",
    ) -> dict[str, Any]:
        """Run or stop a bounded preview/final compile; never enables shell escape or rc files."""

        if action == "stop":
            concurrency.cancel_pending_compiles()
            return workspace.compile_project(action="stop")
        timeout = PREVIEW_TIMEOUT_SECONDS if purpose == "preview" else FINAL_TIMEOUT_SECONDS
        with workspace.compile_request_scope() as request_generation:
            with concurrency.exclusive("compile", timeout_seconds=timeout) as deadline:
                return workspace.compile_project(
                    action=action,
                    root_path=root_path,
                    purpose=purpose,
                    engine=engine,
                    assemble_blocks=assemble_blocks,
                    expected_project_sha256=expected_project_sha256,
                    deadline_monotonic=deadline,
                    request_generation=request_generation,
                )

    @server.tool(annotations=read_only)
    @anticipated_errors
    def recognize_image(kind: RecognitionKind, image_path: str, temperature: float = 0.01) -> dict[str, Any]:
        """Run installed local OCR and return a review-only candidate without writing."""

        with concurrency.recognition():
            return workspace.recognize_image(kind, image_path, temperature=temperature)

    @server.tool(annotations=network)
    @anticipated_errors
    def fetch_reference_metadata(raw_text: str) -> dict[str, Any]:
        """Fetch DOI or arXiv BibTeX through ICSTeX's fixed HTTPS allowlist."""

        with concurrency.network():
            return workspace.fetch_reference_metadata(raw_text)

    @server.tool(annotations=additive)
    @anticipated_errors
    def export_artifact(
        kind: ExportKind,
        target_path: str,
        root_path: str = "main.tex",
        assemble_blocks: bool = False,
        expected_project_sha256: str = "",
    ) -> dict[str, Any]:
        """Export a fresh final PDF or portable project into the host-approved export root."""

        if kind == "pdf":
            with workspace.compile_request_scope() as request_generation:
                with concurrency.exclusive("compile", timeout_seconds=FINAL_TIMEOUT_SECONDS) as deadline:
                    return workspace.export_artifact(
                        kind,
                        target_path,
                        root_path=root_path,
                        assemble_blocks=assemble_blocks,
                        expected_project_sha256=expected_project_sha256,
                        deadline_monotonic=deadline,
                        request_generation=request_generation,
                    )
        with concurrency.exclusive():
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
