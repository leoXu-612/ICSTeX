"""Project-scoped operations for local Agents and Harnesses.

This module has no MCP or GUI dependency.  A workspace is bound to one
canonical project root; every mutation is permission-gated and compare-and-
swap protected.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import uuid
from typing import Iterator

from app import __app_name__, __version__
from app.core.blocks.assembly import build_latex_files
from app.core.blocks.export_package import export_package
from app.core.blocks.layout import LayoutNode
from app.core.blocks.model import Block
from app.core.blocks.project_repository import load_project
from app.core.blocks.registry import BlockError, BlockRegistry, CreateBlockInput
from app.core.blocks.schema import validate_layout, validate_source, validate_theme
from app.core.blocks.source_registry import SourceRecord
from app.core.blocks.theme import DocumentTheme, theme_from_dict
from app.core.compiler import (
    FINAL_TIMEOUT_SECONDS,
    PREVIEW_TIMEOUT_SECONDS,
    BuildPurpose,
    CompileManager,
    CompileResult,
)
from app.core.diagnostics import analyze_project
from app.core.formula.sanitizer import sanitize_formula_latex
from app.core.image_assets import IMAGE_SUFFIXES
from app.core.latex_outline import scan_outline
from app.core.latex_tools import LaTeXEngine, LaTeXToolchain, detect_toolchain
from app.core.log_parser import parse_log_file
from app.core.magic_comments import parse_magic_comments
from app.core.paths import ROOT_CANDIDATES, strip_latex_comments
from app.core.project_tools import (
    bib_keys,
    duplicate_labels,
    fetch_bib_online,
    scan_citations,
    scan_labels,
    scan_references,
    undefined_citations,
    undefined_references,
)
from app.core.search import SearchOptions, find_matches
from app.core.synctex import pdf_to_source, source_to_pdf
from app.core.text_encoding import decode_latex_bytes
from app.core.word_count import count_project


MAX_TEXT_BYTES = 16 * 1024 * 1024
MAX_ASSET_BYTES = 128 * 1024 * 1024
MAX_PROJECT_FILES = 20_000
MAX_WORKER_OUTPUT_BYTES = 4 * 1024 * 1024
TEXT_SUFFIXES = {".tex", ".bib", ".sty", ".cls", ".json", ".md", ".txt", ".csv", ".tsv", ".log"}
WRITABLE_TEXT_SUFFIXES = TEXT_SUFFIXES - {".log"}
INTERNAL_WRITE_DIRS = {".icstex", ".latex_build", "__pycache__", ".git"}
SNAPSHOT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BLOCK_STATE_PATHS = {
    ".icstex/blocks.json",
    ".icstex/layouts.json",
    ".icstex/sources.json",
    "styles/document-theme.json",
}


class AgentWorkspaceError(RuntimeError):
    """Base error surfaced through the protocol layer."""


class CapabilityDenied(AgentWorkspaceError):
    pass


class ConflictError(AgentWorkspaceError):
    pass


class UnsafePathError(AgentWorkspaceError):
    pass


@dataclass(frozen=True)
class AgentGrants:
    allow_write: bool = False
    allow_compile: bool = False
    allow_network: bool = False
    allow_recognition: bool = False
    allow_trusted_raw_latex: bool = False
    export_root: Path | None = None
    allowed_inputs: tuple[Path, ...] = ()


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


class AgentWorkspace:
    """Safe, semantic ICSTeX operations bound to one project root."""

    def __init__(self, project_root: str | Path, *, grants: AgentGrants | None = None) -> None:
        self.root = _canonical_directory(project_root, label="project root")
        requested = grants or AgentGrants()
        export_root = (
            _canonical_directory(requested.export_root, label="export root")
            if requested.export_root is not None
            else None
        )
        inputs = tuple(_canonical_input(path) for path in requested.allowed_inputs)
        self.grants = AgentGrants(
            allow_write=requested.allow_write,
            allow_compile=requested.allow_compile,
            allow_network=requested.allow_network,
            allow_recognition=requested.allow_recognition,
            allow_trusted_raw_latex=requested.allow_trusted_raw_latex,
            export_root=export_root,
            allowed_inputs=inputs,
        )
        self._inputs = {f"input_{index}": path for index, path in enumerate(inputs, start=1)}
        self._compile_managers: dict[str, CompileManager] = {}
        self._compile_lock = threading.Lock()

    # -- public read operations -----------------------------------------
    def inspect_project(self) -> dict:
        detected_root = self._detect_root_file()
        root_file = self._relative_or_none(detected_root)
        tex_files = [self._relative(path) for path in self._iter_files({".tex"})]
        bib_files = [self._relative(path) for path in self._iter_files({".bib"})]
        toolchain = detect_toolchain()
        return {
            "projectRoot": str(self.root),
            "rootFile": root_file,
            "rootSource": "detected" if detected_root is not None else "unknown",
            "texFiles": tex_files,
            "bibFiles": bib_files,
            "blockProject": (self.root / ".icstex" / "blocks.json").is_file(),
            "blockProjectSha256": self.block_project_sha256(),
            "toolchain": {
                "compileReady": toolchain.is_compile_ready,
                "compiler": toolchain.compiler_name,
                "engines": {
                    engine.value: toolchain.supports_engine(engine)
                    for engine in LaTeXEngine
                },
                "synctex": bool(toolchain.synctex),
                "texcount": bool(toolchain.texcount),
            },
            "grants": {
                "write": self.grants.allow_write,
                "compile": self.grants.allow_compile,
                "network": self.grants.allow_network,
                "recognition": self.grants.allow_recognition,
                "trustedRawLatex": self.grants.allow_trusted_raw_latex,
                "export": self.grants.export_root is not None,
            },
            "allowedInputs": [
                {"id": input_id, "name": path.name, "kind": "directory" if path.is_dir() else "file"}
                for input_id, path in self._inputs.items()
            ],
            "interactionBoundary": {
                "guiRemoteControl": False,
                "unsavedGuiBuffers": False,
                "sameProjectGuiMode": "closed-or-read-only",
                "recognitionWrites": False,
            },
        }

    def read_document(self, path: str, *, snapshot_id: str = "") -> dict:
        target = self._project_path(path, must_exist=True, regular=True)
        if target.suffix.lower() not in TEXT_SUFFIXES:
            raise UnsafePathError(f"不是允许读取的文本类型：{target.suffix}")
        if snapshot_id:
            payload, metadata = self._read_snapshot(target, snapshot_id)
        else:
            payload = self._read_limited(target, MAX_TEXT_BYTES)
            metadata = None
        decoded = decode_latex_bytes(payload)
        result = {
            "path": self._relative(target),
            "text": decoded.text,
            "encoding": decoded.encoding,
            "sha256": _sha256(payload),
            "size": len(payload),
        }
        if metadata is not None:
            result["snapshot"] = metadata
        return result

    def query_project(
        self,
        kind: str,
        *,
        path: str = "main.tex",
        query: str = "",
        case_sensitive: bool = False,
        whole_word: bool = False,
        line: int = 1,
        page: int = 1,
        x: float = 0.0,
        y: float = 0.0,
    ) -> dict:
        selected = kind.strip().lower()
        if selected == "search":
            return {"kind": selected, "results": self._search(query, case_sensitive, whole_word)}
        if selected == "history":
            target = self._project_path(path, must_exist=False)
            return {"kind": selected, "path": self._relative(target), "snapshots": self._snapshot_list(target)}
        if selected == "environment":
            toolchain = detect_toolchain()
            tool_names = ("latexmk", "pdflatex", "xelatex", "lualatex", "biber", "bibtex", "texcount", "synctex")
            return {
                "kind": selected,
                "app": {"name": __app_name__, "version": __version__},
                "system": sys.platform,
                "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "compileReady": toolchain.is_compile_ready,
                "tools": [
                    {"name": name, "available": bool(getattr(toolchain, name, None))}
                    for name in tool_names
                ],
                "recommendations": (
                    []
                    if toolchain.is_compile_ready
                    else ["安装 MacTeX、TeX Live 或 MiKTeX，并确认编译器位于 PATH。"]
                ),
            }
        if selected == "assets":
            return {
                "kind": selected,
                "assets": [
                    {"path": self._relative(item), "size": item.stat().st_size, "sha256": _sha256_file(item)}
                    for item in self._iter_files(IMAGE_SUFFIXES)
                ],
            }
        if selected == "blocks":
            return {"kind": selected, **self._block_state()}
        if selected == "synctex-pdf-to-source":
            self._require("compile")
            pdf = self._project_path(path, must_exist=True, regular=True)
            if pdf.suffix.lower() != ".pdf":
                raise UnsafePathError("SyncTeX 反查输入必须是 PDF。")
            position = pdf_to_source(pdf, max(1, int(page)), float(x), float(y))
            return {"kind": selected, "position": self._sync_position(position)}

        root_file = self._root_file(path)
        self._validate_tex_closure(root_file)
        text = self._read_text(root_file)
        if selected == "outline":
            return {"kind": selected, "path": self._relative(root_file), "items": [_plain(item) for item in scan_outline(text)]}
        if selected == "word-count":
            # Read-only MCP sessions must not start texcount.  The deterministic
            # Python fallback still reports its mode explicitly.
            no_tools = LaTeXToolchain(latexmk=None, pdflatex=None, xelatex=None, lualatex=None)
            return {
                "kind": selected,
                "path": self._relative(root_file),
                "result": _plain(count_project(root_file, toolchain=no_tools)),
            }
        if selected == "references":
            combined = self._combined_tex_text(root_file)
            bib_text = self._combined_bib_text()
            return {
                "kind": selected,
                "labels": [_plain(item) for item in scan_labels(combined)],
                "references": sorted(scan_references(combined)),
                "citations": sorted(scan_citations(combined)),
                "bibKeys": sorted(bib_keys(bib_text)),
                "duplicateLabels": sorted(duplicate_labels(combined)),
                "undefinedReferences": sorted(undefined_references(combined)),
                "undefinedCitations": sorted(undefined_citations(combined, bib_text)),
            }
        if selected == "diagnostics":
            self._validate_resource_references(text, root_file.parent)
            log_path = self.root / ".latex_build" / f"{root_file.stem}.log"
            log_errors = []
            if log_path.exists():
                self._assert_project_file(log_path, must_exist=True)
                log_errors = parse_log_file(log_path, self.root)
            diagnostics = analyze_project(
                text,
                root_file=root_file,
                bib_text=self._combined_bib_text(),
                toolchain=detect_toolchain(),
                log_errors=log_errors,
            )
            return {"kind": selected, "path": self._relative(root_file), "diagnostics": [self._diagnostic(item) for item in diagnostics]}
        if selected == "synctex-source-to-pdf":
            self._require("compile")
            source = self._project_path(path, must_exist=True, regular=True)
            pdf = self.root / ".latex_build" / f"{root_file.stem}.pdf"
            self._assert_project_file(pdf, must_exist=True)
            position = source_to_pdf(source, max(1, int(line)), pdf)
            return {"kind": selected, "position": self._sync_position(position)}
        raise AgentWorkspaceError(
            "未知查询；可用值：search, history, environment, assets, blocks, outline, "
            "word-count, references, diagnostics, synctex-source-to-pdf, synctex-pdf-to-source"
        )

    # -- public mutations ------------------------------------------------
    def write_document(
        self,
        path: str,
        text: str,
        *,
        expected_sha256: str,
        encoding: str = "",
    ) -> dict:
        self._require("write")
        target = self._project_path(path, must_exist=False)
        if target.suffix.lower() not in WRITABLE_TEXT_SUFFIXES:
            raise UnsafePathError(f"不是允许写入的文本类型：{target.suffix}")
        if target.relative_to(self.root).parts[0] in INTERNAL_WRITE_DIRS:
            raise UnsafePathError("内部状态必须通过语义工具修改。")
        with self._project_lock():
            current = self._current_bytes(target, MAX_TEXT_BYTES)
            self._check_expected(current, expected_sha256)
            selected_encoding = encoding.strip() or (
                decode_latex_bytes(current).encoding if current is not None else "utf-8"
            )
            try:
                payload = text.encode(selected_encoding)
            except (LookupError, UnicodeEncodeError) as exc:
                raise AgentWorkspaceError(f"无法使用 {selected_encoding} 编码写入：{exc}") from exc
            if len(payload) > MAX_TEXT_BYTES:
                raise AgentWorkspaceError(f"文本超过 {MAX_TEXT_BYTES} 字节限制。")
            snapshot = self._snapshot_preimage(target, current, selected_encoding)
            try:
                self._atomic_write_bytes(target, payload)
            except BaseException:
                if snapshot is not None:
                    self._remove_snapshot_entry(snapshot)
                raise
        return {
            "path": self._relative(target),
            "oldSha256": _sha256(current) if current is not None else None,
            "sha256": _sha256(payload),
            "encoding": selected_encoding,
            "size": len(payload),
            "snapshotId": snapshot,
        }

    def restore_snapshot(
        self,
        path: str,
        snapshot_id: str,
        *,
        expected_sha256: str,
    ) -> dict:
        """CAS-restore a verified text or image preimage."""

        self._require("write")
        target = self._project_path(path, must_exist=False)
        if target.suffix.lower() not in WRITABLE_TEXT_SUFFIXES | IMAGE_SUFFIXES:
            raise UnsafePathError(f"不支持恢复该文件类型：{target.suffix}")
        with self._project_lock():
            current = self._current_bytes(target, MAX_ASSET_BYTES)
            self._check_expected(current, expected_sha256)
            payload, restored = self._read_snapshot(target, snapshot_id)
            relative = self._relative(target)
            if target.relative_to(self.root).parts[0] in INTERNAL_WRITE_DIRS and relative not in BLOCK_STATE_PATHS:
                raise UnsafePathError("内部状态只能通过对应的语义恢复路径修改。")
            undo_snapshot = self._snapshot_preimage(
                target,
                current,
                "binary" if target.suffix.lower() in IMAGE_SUFFIXES else str(restored.get("encoding", "utf-8")),
            )
            try:
                self._atomic_write_bytes(target, payload)
                if relative in BLOCK_STATE_PATHS:
                    self._load_block_state()
            except BaseException as original:
                try:
                    if current is None:
                        target.unlink(missing_ok=True)
                    else:
                        self._atomic_write_bytes(target, current)
                except OSError as rollback_error:
                    raise AgentWorkspaceError(f"快照恢复失败且回滚不完整：{rollback_error}") from original
                if undo_snapshot is not None:
                    self._remove_snapshot_entry(undo_snapshot)
                if isinstance(original, AgentWorkspaceError):
                    raise
                raise AgentWorkspaceError(f"快照内容校验失败：{original}") from original
        return {
            "path": self._relative(target),
            "restoredSnapshotId": snapshot_id,
            "undoSnapshotId": undo_snapshot,
            "sha256": _sha256(payload),
            "size": len(payload),
        }

    def import_asset(
        self,
        input_id: str,
        destination_path: str,
        *,
        source_path: str = "",
        expected_sha256: str = "missing",
    ) -> dict:
        self._require("write")
        source = self._input_file(input_id, source_path)
        if source.suffix.lower() not in IMAGE_SUFFIXES:
            raise UnsafePathError(f"不支持的图片类型：{source.suffix}")
        destination = self._project_path(destination_path, must_exist=False)
        relative = destination.relative_to(self.root)
        if not relative.parts or relative.parts[0] not in {"figures", "assets"}:
            raise UnsafePathError("图片只能导入 figures/ 或 assets/。")
        if destination.suffix.lower() not in IMAGE_SUFFIXES:
            raise UnsafePathError(f"不支持的图片类型：{destination.suffix}")
        payload = self._read_limited(source, MAX_ASSET_BYTES)
        with self._project_lock():
            current = self._current_bytes(destination, MAX_ASSET_BYTES)
            self._check_expected(current, expected_sha256)
            snapshot = self._snapshot_preimage(destination, current, "binary")
            try:
                self._atomic_write_bytes(destination, payload)
            except BaseException:
                if snapshot is not None:
                    self._remove_snapshot_entry(snapshot)
                raise
        return {
            "path": self._relative(destination),
            "sha256": _sha256(payload),
            "size": len(payload),
            "snapshotId": snapshot,
        }

    def mutate_blocks(
        self,
        operation: str,
        payload: dict,
        *,
        expected_project_sha256: str,
    ) -> dict:
        self._require("write")
        selected = operation.strip().lower()
        with self._project_lock():
            self._check_project_etag(expected_project_sha256)
            state = self._load_block_state()
            registry: BlockRegistry = state["registry"]
            layout: LayoutNode | None = state["layout"]
            sources: list[SourceRecord] = state["sources"]
            theme: DocumentTheme = state["document_theme"]

            if selected == "create":
                block = registry.create(self._create_block_input(payload))
                self._save_registry(registry)
                changed = {"block": block.to_dict()}
            elif selected == "update":
                block_id = str(payload.get("blockId", ""))
                block = self._expected_block(registry, block_id, payload.get("expectedRevision"))
                patch = self._block_patch(payload.get("patch", {}), block)
                changed_block = registry.update(block_id, patch)
                self._save_registry(registry)
                changed = {"block": changed_block.to_dict()}
            elif selected == "delete":
                block_id = str(payload.get("blockId", ""))
                self._expected_block(registry, block_id, payload.get("expectedRevision"))
                registry.remove(block_id, str(payload.get("strategy", "reject-if-referenced")))
                self._save_registry(registry)
                changed = {"deletedBlockId": block_id}
            elif selected == "set-layout":
                raw_layout = payload.get("layout")
                if raw_layout is None:
                    layout = None
                elif not isinstance(raw_layout, dict):
                    raise AgentWorkspaceError("layout 必须是对象或 null。")
                else:
                    issues = validate_layout(raw_layout)
                    if issues:
                        raise AgentWorkspaceError("布局校验失败：" + "; ".join(issues[:5]))
                    layout = LayoutNode.from_dict(raw_layout)
                    self._validate_layout_references(layout, registry)
                self._write_json_state(
                    self.root / ".icstex" / "layouts.json",
                    {"schemaVersion": "1.0.0", "layouts": [layout.to_dict()] if layout else []},
                )
                changed = {"layout": layout.to_dict() if layout else None}
            elif selected == "set-theme":
                raw_theme = payload.get("theme")
                if not isinstance(raw_theme, dict):
                    raise AgentWorkspaceError("theme 必须是对象。")
                issues = validate_theme(raw_theme)
                if issues:
                    raise AgentWorkspaceError("主题校验失败：" + "; ".join(issues[:5]))
                parsed_theme = theme_from_dict(raw_theme)
                if not isinstance(parsed_theme, DocumentTheme):
                    raise AgentWorkspaceError("MCP 只修改文档主题，不修改 App 主题。")
                theme = parsed_theme
                self._write_json_state(self.root / "styles" / "document-theme.json", theme.to_dict())
                changed = {"theme": theme.to_dict()}
            elif selected == "set-sources":
                raw_sources = payload.get("sources")
                if not isinstance(raw_sources, list):
                    raise AgentWorkspaceError("sources 必须是数组。")
                parsed_sources: list[SourceRecord] = []
                for raw_source in raw_sources:
                    if not isinstance(raw_source, dict):
                        raise AgentWorkspaceError("每个 source 必须是对象。")
                    issues = validate_source(raw_source)
                    if issues:
                        raise AgentWorkspaceError("来源校验失败：" + "; ".join(issues[:5]))
                    record = SourceRecord.from_dict(raw_source)
                    self._project_path(record.relativePath, must_exist=False)
                    parsed_sources.append(record)
                sources = parsed_sources
                self._write_json_state(
                    self.root / ".icstex" / "sources.json",
                    {"sources": [record.to_dict() for record in sources]},
                )
                changed = {"sources": [record.to_dict() for record in sources]}
            elif selected == "assemble":
                if not (self.root / ".icstex" / "blocks.json").is_file():
                    raise AgentWorkspaceError("当前目录不是已保存的 Block 项目，拒绝覆盖 main.tex。")
                files = build_latex_files(
                    self.root,
                    registry=registry,
                    layout=layout,
                    document_theme=theme,
                    allow_trusted_raw_latex=self.grants.allow_trusted_raw_latex,
                )
                self._write_generated_transaction(files)
                changed = {"generated": [self._relative(path) for path in sorted(files)]}
            else:
                raise AgentWorkspaceError(
                    "未知 Block 操作；可用值：create, update, delete, set-layout, set-theme, set-sources, assemble"
                )
            next_etag = self.block_project_sha256()
        return {"operation": selected, **changed, "blockProjectSha256": next_etag}

    # -- execution, recognition, network, export -------------------------
    def compile_project(
        self,
        *,
        action: str = "run",
        root_path: str = "main.tex",
        purpose: str = "preview",
        engine: str = "auto",
        assemble_blocks: bool = False,
        expected_project_sha256: str = "",
    ) -> dict:
        self._require("compile")
        if action == "stop":
            stopped = False
            with self._compile_lock:
                managers = list(self._compile_managers.values())
            for manager in managers:
                stopped = manager.stop_current(timeout=1.5) or stopped
            return {"action": "stop", "stopped": stopped}
        if action != "run":
            raise AgentWorkspaceError("action 必须是 run 或 stop。")
        if assemble_blocks:
            if not expected_project_sha256:
                raise ConflictError("组装 Block 项目必须提供 expected_project_sha256。")
            self.mutate_blocks("assemble", {}, expected_project_sha256=expected_project_sha256)
        root_file = self._root_file(root_path)
        self._validate_executable_tree()
        self._validate_tex_closure(root_file)
        selected_purpose = BuildPurpose(purpose)
        selected_engine = LaTeXEngine(engine)
        manager = CompileManager(
            root_file,
            toolchain=detect_toolchain(),
            engine=selected_engine,
            restricted_io=True,
        )
        key = self._relative(root_file)
        with self._compile_lock:
            self._compile_managers[key] = manager
        timeout = PREVIEW_TIMEOUT_SECONDS if selected_purpose is BuildPurpose.PREVIEW else FINAL_TIMEOUT_SECONDS
        try:
            result = manager.compile_now(selected_purpose, timeout_seconds=timeout)
        finally:
            with self._compile_lock:
                self._compile_managers.pop(key, None)
        if result is None:
            raise AgentWorkspaceError("编译未启动。")
        return self._compile_result(result)

    def fetch_reference_metadata(self, raw_text: str) -> dict:
        self._require("network")
        if len(raw_text) > 4096:
            raise AgentWorkspaceError("元数据查询输入超过 4096 字符限制。")
        result = fetch_bib_online(raw_text)
        return {"found": result is not None, "result": _plain(result) if result is not None else None}

    def recognize_image(self, kind: str, image_path: str, *, temperature: float = 0.01) -> dict:
        self._require("recognition")
        selected = kind.strip().lower()
        if selected not in {"formula", "text"}:
            raise AgentWorkspaceError("kind 必须是 formula 或 text。")
        image = self._project_path(image_path, must_exist=True, regular=True)
        if image.suffix.lower() not in IMAGE_SUFFIXES:
            raise UnsafePathError("识别输入必须是项目内支持的图片。")
        if not math.isfinite(temperature) or not 0.0 <= temperature <= 2.0:
            raise AgentWorkspaceError("temperature 必须是 0 到 2 之间的有限数值。")
        if selected == "formula":
            response = self._recognize_formula(image, temperature)
            candidate = str(response.get("latex", ""))
            sanitized = sanitize_formula_latex(candidate)
            return {
                "kind": selected,
                "provider": "pix2tex",
                "candidate": sanitized.text,
                "safe": sanitized.ok,
                "warnings": list(sanitized.warnings),
                "errors": list(sanitized.errors),
                "reviewRequired": True,
                "elapsedMs": response.get("elapsed_ms"),
            }
        response = self._recognize_text(image)
        return {
            "kind": selected,
            "provider": "rapidocr",
            "candidate": str(response.get("text", "")),
            "regions": response.get("regions", []),
            "reviewRequired": True,
            "elapsedMs": response.get("elapsedMs"),
        }

    def export_artifact(
        self,
        kind: str,
        target_path: str,
        *,
        root_path: str = "main.tex",
        assemble_blocks: bool = False,
        expected_project_sha256: str = "",
    ) -> dict:
        if self.grants.export_root is None:
            raise CapabilityDenied("未授予导出目录；请由宿主使用 --export-root 启动。")
        target = self._export_path(target_path)
        if target.is_relative_to(self.root) or self.root.is_relative_to(target):
            raise UnsafePathError("导出目标不能与项目目录重叠。")
        if target.exists() or target.is_symlink():
            raise ConflictError("导出目标已存在；为避免覆盖，请使用新的目标名称。")
        selected = kind.strip().lower()
        if selected == "pdf":
            result = self.compile_project(
                root_path=root_path,
                purpose="final",
                assemble_blocks=assemble_blocks,
                expected_project_sha256=expected_project_sha256,
            )
            if not result["ok"]:
                raise AgentWorkspaceError("最终编译失败，未导出 PDF。")
            source = self._project_path(result["pdfFile"], must_exist=True, regular=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_copy(source, target)
            return {"kind": selected, "target": target_path, "sha256": _sha256_file(target), "size": target.stat().st_size}
        if selected == "package":
            if assemble_blocks:
                if not expected_project_sha256:
                    raise ConflictError("组装 Block 项目必须提供 expected_project_sha256。")
                self.mutate_blocks("assemble", {}, expected_project_sha256=expected_project_sha256)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
            try:
                result = export_package(self.root, temporary)
                os.replace(temporary, target)
            except BaseException:
                shutil.rmtree(temporary, ignore_errors=True)
                raise
            return {"kind": selected, "target": target_path, "files": list(result.files), "manifest": result.manifest}
        raise AgentWorkspaceError("kind 必须是 pdf 或 package。")

    # -- Block helpers ---------------------------------------------------
    def block_project_sha256(self) -> str:
        self._validate_block_state_paths()
        digest = hashlib.sha256()
        for relative in (
            ".icstex/blocks.json",
            ".icstex/layouts.json",
            ".icstex/sources.json",
            "styles/document-theme.json",
        ):
            path = self.root / relative
            digest.update(relative.encode("utf-8") + b"\0")
            if path.exists():
                self._assert_project_file(path, must_exist=True)
                digest.update(self._read_limited(path, MAX_TEXT_BYTES))
            else:
                digest.update(b"<missing>")
            digest.update(b"\0")
        return digest.hexdigest()

    def _block_state(self) -> dict:
        state = self._load_block_state()
        registry: BlockRegistry = state["registry"]
        sources: list[SourceRecord] = state["sources"]
        return {
            "blockProjectSha256": self.block_project_sha256(),
            "blocks": [block.to_dict() for block in registry.blocks()],
            "layout": state["layout"].to_dict() if state["layout"] else None,
            "theme": state["document_theme"].to_dict(),
            "sources": [self._source_state(record) for record in sources],
            "issues": [_plain(issue) for issue in registry.validate_all()],
        }

    def _create_block_input(self, payload: dict) -> CreateBlockInput:
        if not isinstance(payload, dict):
            raise AgentWorkspaceError("Block payload 必须是对象。")
        helper = Block.from_dict(payload)
        return CreateBlockInput(
            type=str(payload.get("type", "text")),
            alias=str(payload.get("alias", "")),
            semantic=helper.semantic,
            content=dict(payload.get("content", {})),
            references=helper.references,
            provenance=helper.provenance,
            metadata=dict(payload.get("metadata", {})),
            extensions=dict(payload.get("extensions", {})),
        )

    def _block_patch(self, raw_patch: object, block: Block) -> dict:
        if not isinstance(raw_patch, dict):
            raise AgentWorkspaceError("patch 必须是对象。")
        allowed = {"alias", "semantic", "content", "references", "metadata", "extensions"}
        unknown = set(raw_patch) - allowed
        if unknown:
            raise AgentWorkspaceError("不允许修改字段：" + ", ".join(sorted(unknown)))
        patch = dict(raw_patch)
        helper_payload = block.to_dict()
        if "semantic" in patch:
            helper_payload["semantic"] = patch["semantic"]
            patch["semantic"] = Block.from_dict(helper_payload).semantic
        if "references" in patch:
            helper_payload["references"] = patch["references"]
            patch["references"] = Block.from_dict(helper_payload).references
        return patch

    @staticmethod
    def _expected_block(registry: BlockRegistry, block_id: str, expected_revision: object) -> Block:
        block = registry.get(block_id)
        if block is None:
            raise BlockError(f"Block 不存在：{block_id}")
        try:
            revision = int(expected_revision)
        except (TypeError, ValueError) as exc:
            raise ConflictError("必须提供 expectedRevision。") from exc
        if block.revision != revision:
            raise ConflictError(f"Block revision 冲突：当前 {block.revision}，提交 {revision}。")
        return block

    def _save_registry(self, registry: BlockRegistry) -> None:
        issues = registry.validate_all()
        if issues:
            raise AgentWorkspaceError("拒绝保存无效 Block：" + "; ".join(issue.message for issue in issues[:5]))
        payload = {
            "format": "icstex-blocks",
            "schemaVersion": "1.0.0",
            "blocks": [block.to_dict() for block in registry.blocks()],
        }
        self._write_json_state(self.root / ".icstex" / "blocks.json", payload)

    def _write_json_state(self, path: Path, payload: dict) -> None:
        current = self._current_bytes(path, MAX_TEXT_BYTES)
        snapshot = self._snapshot_preimage(path, current, "utf-8")
        data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if len(data) > MAX_TEXT_BYTES:
            if snapshot is not None:
                self._remove_snapshot_entry(snapshot)
            raise AgentWorkspaceError(f"状态 JSON 超过 {MAX_TEXT_BYTES} 字节限制。")
        try:
            self._atomic_write_bytes(path, data)
        except BaseException:
            if snapshot is not None:
                self._remove_snapshot_entry(snapshot)
            raise

    def _load_block_state(self) -> dict:
        """Strictly validate persisted state before the tolerant GUI loader sees it."""

        self._validate_block_state_paths()
        metadata = self.root / ".icstex"
        layouts_path = metadata / "layouts.json"
        if layouts_path.is_file():
            payload = self._read_json_object(layouts_path)
            layouts = payload.get("layouts")
            if not isinstance(layouts, list) or len(layouts) > 1:
                raise AgentWorkspaceError("layouts.json 必须包含零或一个布局。")
            if layouts:
                if not isinstance(layouts[0], dict):
                    raise AgentWorkspaceError("布局必须是对象。")
                issues = validate_layout(layouts[0])
                if issues:
                    raise AgentWorkspaceError("持久化布局无效：" + "; ".join(issues[:5]))
        sources_path = metadata / "sources.json"
        if sources_path.is_file():
            payload = self._read_json_object(sources_path)
            sources = payload.get("sources")
            if not isinstance(sources, list):
                raise AgentWorkspaceError("sources.json 的 sources 必须是数组。")
            for source in sources:
                if not isinstance(source, dict):
                    raise AgentWorkspaceError("持久化来源必须是对象。")
                issues = validate_source(source)
                if issues:
                    raise AgentWorkspaceError("持久化来源无效：" + "; ".join(issues[:5]))
        theme_path = self.root / "styles" / "document-theme.json"
        if theme_path.is_file():
            payload = self._read_json_object(theme_path)
            issues = validate_theme(payload)
            if issues:
                raise AgentWorkspaceError("持久化主题无效：" + "; ".join(issues[:5]))
        state = load_project(self.root)
        if state["layout"] is not None:
            self._validate_layout_references(state["layout"], state["registry"])
        return state

    def _read_json_object(self, path: Path) -> dict:
        try:
            payload = json.loads(self._read_limited(path, MAX_TEXT_BYTES).decode("utf-8"))
        except (UnicodeError, ValueError) as exc:
            raise AgentWorkspaceError(f"状态 JSON 无法解析：{self._relative(path)}") from exc
        if not isinstance(payload, dict):
            raise AgentWorkspaceError(f"状态 JSON 必须是对象：{self._relative(path)}")
        return payload

    def _validate_layout_references(self, layout: LayoutNode, registry: BlockRegistry) -> None:
        def walk(node: object) -> Iterator[str]:
            if hasattr(node, "blockId"):
                yield str(getattr(node, "blockId"))
            for child in getattr(node, "children", ()):
                yield from walk(child)

        missing = sorted({block_id for block_id in walk(layout) if registry.get(block_id) is None})
        if missing:
            raise AgentWorkspaceError("布局引用不存在的 Block：" + ", ".join(missing))

    def _write_generated_transaction(self, files: dict[Path, str]) -> None:
        before: dict[Path, bytes | None] = {}
        written: list[Path] = []
        snapshots: list[str] = []
        for path in files:
            self._assert_project_file(path, must_exist=False)
            before[path] = self._current_bytes(path, MAX_TEXT_BYTES)
        try:
            for path, text in files.items():
                payload = text.encode("utf-8")
                if len(payload) > MAX_TEXT_BYTES:
                    raise AgentWorkspaceError(f"生成文件超过 {MAX_TEXT_BYTES} 字节限制。")
                if before[path] == payload:
                    continue
                snapshot = self._snapshot_preimage(path, before[path], "utf-8")
                if snapshot is not None:
                    snapshots.append(snapshot)
                self._atomic_write_bytes(path, payload)
                written.append(path)
        except BaseException as original:
            failures: list[str] = []
            for path in reversed(written):
                try:
                    if before[path] is None:
                        path.unlink(missing_ok=True)
                    else:
                        self._atomic_write_bytes(path, before[path] or b"")
                except OSError as exc:
                    failures.append(f"{self._relative(path)}: {exc}")
            if failures:
                raise AgentWorkspaceError("生成失败且回滚不完整：" + "; ".join(failures)) from original
            for snapshot_id in snapshots:
                self._remove_snapshot_entry(snapshot_id)
            raise

    # -- path, CAS, snapshot, lock helpers -------------------------------
    def _project_path(self, relative: str, *, must_exist: bool, regular: bool = False) -> Path:
        parts = _safe_relative_parts(relative)
        path = self.root.joinpath(*parts)
        self._assert_project_file(path, must_exist=must_exist)
        if regular and not _is_regular(path):
            raise UnsafePathError(f"不是普通文件：{relative}")
        return path

    def _assert_project_file(self, path: Path, *, must_exist: bool) -> None:
        lexical = Path(os.path.abspath(path))
        try:
            lexical.relative_to(self.root)
        except ValueError as exc:
            raise UnsafePathError("路径越出项目目录。") from exc
        current = self.root
        relative = lexical.relative_to(self.root)
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise UnsafePathError(f"拒绝符号链接路径：{relative.as_posix()}")
            if current.exists() and current != lexical and not current.is_dir():
                raise UnsafePathError(f"路径父级不是目录：{relative.as_posix()}")
        if must_exist:
            if not lexical.exists():
                raise UnsafePathError(f"文件不存在：{relative.as_posix()}")
            resolved = lexical.resolve(strict=True)
        else:
            parent = lexical.parent
            while not parent.exists() and parent != self.root:
                parent = parent.parent
            if parent.is_symlink() or not parent.resolve(strict=True).is_relative_to(self.root):
                raise UnsafePathError("路径越出项目目录。")
            resolved = lexical.resolve(strict=False)
        if not resolved.is_relative_to(self.root):
            raise UnsafePathError("路径越出项目目录。")

    def _root_file(self, path: str) -> Path:
        selected = self._project_path(path, must_exist=True, regular=True)
        if selected.suffix.lower() != ".tex":
            raise UnsafePathError("编译根必须是 .tex 文件。")
        magic_root = parse_magic_comments(self._read_text(selected), base_dir=selected.parent).root
        if magic_root is not None:
            self._assert_project_file(magic_root, must_exist=True)
            if magic_root.suffix.lower() != ".tex" or not _is_regular(magic_root):
                raise UnsafePathError("Magic Root 不是项目内普通 .tex 文件。")
            if selected not in self._safe_tex_closure(magic_root):
                raise UnsafePathError("Magic Root 没有包含当前文件。")
            return magic_root
        if self._is_latex_root(selected):
            return selected
        candidates: list[tuple[tuple[int, int, str], Path]] = []
        for candidate in self._iter_files({".tex"}):
            if candidate == selected or not self._is_latex_root(candidate):
                continue
            closure = self._safe_tex_closure(candidate)
            if selected in closure:
                name_score = (
                    len(ROOT_CANDIDATES) - ROOT_CANDIDATES.index(candidate.name.lower())
                    if candidate.name.lower() in ROOT_CANDIDATES
                    else 0
                )
                candidates.append(((len(closure), name_score, str(candidate)), candidate))
        if candidates:
            return sorted(candidates, key=lambda item: item[0], reverse=True)[0][1]
        return selected

    def _detect_root_file(self) -> Path | None:
        files = self._iter_files({".tex"})
        by_name = {path.name.lower(): path for path in files}
        for name in ROOT_CANDIDATES:
            candidate = by_name.get(name)
            if candidate is not None and self._is_latex_root(candidate):
                return candidate
        roots = [path for path in files if self._is_latex_root(path)]
        return sorted(roots, key=lambda path: (len(self._safe_tex_closure(path)), str(path)), reverse=True)[0] if roots else (files[0] if files else None)

    def _is_latex_root(self, path: Path) -> bool:
        try:
            text = self._read_text(path)
        except (OSError, UnicodeError, AgentWorkspaceError):
            return False
        return "\\documentclass" in text or "\\begin{document}" in text

    def _safe_tex_closure(self, root_file: Path, *, max_files: int = 200) -> frozenset[Path]:
        queue = [root_file]
        seen: set[Path] = set()
        while queue:
            if len(seen) >= max_files:
                raise AgentWorkspaceError(f"LaTeX 依赖超过 {max_files} 个文件限制。")
            current = queue.pop()
            if current in seen:
                continue
            self._assert_project_file(current, must_exist=False)
            if not current.exists():
                continue
            if current.suffix.lower() != ".tex" or not _is_regular(current):
                raise UnsafePathError(f"LaTeX 依赖不是普通 .tex 文件：{self._relative(current)}")
            seen.add(current)
            text = self._read_text(current)
            for child in self._safe_included_tex_paths(current, text):
                if child.exists() and child not in seen:
                    queue.append(child)
        return frozenset(seen)

    def _safe_included_tex_paths(self, source: Path, text: str) -> tuple[Path, ...]:
        children: list[Path] = []
        for match in re.finditer(r"\\(?:input|include|subfile)\s*\{([^}]+)\}", strip_latex_comments(text)):
            raw = match.group(1).strip()
            if not raw or "\x00" in raw or "\\" in raw or "://" in raw:
                raise UnsafePathError("LaTeX 依赖必须是静态 POSIX 相对路径。")
            candidate = PurePosixPath(raw)
            if candidate.is_absolute():
                raise UnsafePathError("LaTeX 依赖不能使用绝对路径。")
            lexical = source.parent.joinpath(*candidate.parts)
            if lexical.suffix == "":
                lexical = lexical.with_suffix(".tex")
            if lexical.suffix.lower() != ".tex":
                continue
            self._assert_project_file(lexical, must_exist=False)
            children.append(lexical)
        return tuple(dict.fromkeys(children))

    def _validate_tex_closure(self, root_file: Path) -> None:
        self._safe_tex_closure(root_file)

    def _validate_block_state_paths(self) -> None:
        for relative in (
            ".icstex/blocks.json",
            ".icstex/layouts.json",
            ".icstex/sources.json",
            "styles/document-theme.json",
        ):
            path = self.root / relative
            if path.exists() or path.is_symlink():
                self._assert_project_file(path, must_exist=True)
                if not _is_regular(path):
                    raise UnsafePathError(f"Block 状态不是普通文件：{relative}")

    def _validate_resource_references(self, text: str, source_dir: Path) -> None:
        for match in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}", text):
            raw = match.group(1).strip().replace("\\", "/")
            if not raw or "://" in raw or raw.startswith("/"):
                raise UnsafePathError("图片引用必须是项目相对路径。")
            candidate = PurePosixPath(raw)
            if candidate.parts and len(candidate.parts[0]) == 2 and candidate.parts[0][1] == ":":
                raise UnsafePathError("图片引用不能使用 Windows 盘符。")
            if any(part in {"", ".", ".."} for part in candidate.parts):
                raise UnsafePathError("图片引用不能包含 . 或 ..。")
            lexical = source_dir.joinpath(*candidate.parts)
            self._assert_project_file(lexical, must_exist=False)

    def _validate_executable_tree(self) -> None:
        """Reject links and special files that TeX could reach while compiling."""

        for directory, names, filenames in os.walk(self.root, followlinks=False):
            base = Path(directory)
            if base == self.root:
                names[:] = [name for name in names if name != ".git"]
            for name in [*names, *filenames]:
                path = base / name
                relative = path.relative_to(self.root).as_posix()
                try:
                    mode = path.stat(follow_symlinks=False).st_mode
                except OSError as exc:
                    raise UnsafePathError(f"无法安全检查编译输入：{relative}") from exc
                if stat.S_ISLNK(mode):
                    raise UnsafePathError(f"编译输入包含符号链接：{relative}")
                if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                    raise UnsafePathError(f"编译输入包含非普通文件：{relative}")

    def _export_path(self, relative: str) -> Path:
        assert self.grants.export_root is not None
        parts = _safe_relative_parts(relative)
        target = self.grants.export_root.joinpath(*parts)
        current = self.grants.export_root
        for part in parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise UnsafePathError("导出路径包含符号链接。")
        if not target.resolve(strict=False).is_relative_to(self.grants.export_root):
            raise UnsafePathError("导出路径越界。")
        return target

    def _input_file(self, input_id: str, relative: str) -> Path:
        granted = self._inputs.get(input_id)
        if granted is None:
            raise CapabilityDenied("未知输入授权。")
        if granted.is_file():
            if relative not in {"", granted.name}:
                raise UnsafePathError("文件型输入授权不接受子路径。")
            return granted
        parts = _safe_relative_parts(relative)
        candidate = granted.joinpath(*parts)
        current = granted
        for part in parts:
            current = current / part
            if current.is_symlink():
                raise UnsafePathError("输入路径包含符号链接。")
        if not candidate.resolve(strict=True).is_relative_to(granted) or not _is_regular(candidate):
            raise UnsafePathError("输入不是授权目录内的普通文件。")
        return candidate

    @contextmanager
    def _project_lock(self) -> Iterator[None]:
        key = str(self.root)
        with _LOCKS_GUARD:
            thread_lock = _LOCKS.setdefault(key, threading.RLock())
        with thread_lock:
            lock_dir = Path(tempfile.gettempdir()).resolve() / "icstex-agent-locks"
            lock_dir.mkdir(parents=True, exist_ok=True)
            lock_path = lock_dir / f"{_sha256(key.encode('utf-8'))}.lock"
            with lock_path.open("a+b") as handle:
                _lock_handle(handle)
                try:
                    yield
                finally:
                    _unlock_handle(handle)

    def _check_expected(self, current: bytes | None, expected: str) -> None:
        normalized = expected.strip().lower()
        actual = _sha256(current) if current is not None else "missing"
        if normalized != "missing" and not SHA256_RE.fullmatch(normalized):
            raise ConflictError("expected_sha256 必须是 64 位小写 SHA-256 或 missing。")
        if normalized != actual:
            raise ConflictError(f"内容已变化：当前 SHA-256 为 {actual}。")

    def _check_project_etag(self, expected: str) -> None:
        normalized = expected.strip().lower()
        if not SHA256_RE.fullmatch(normalized):
            raise ConflictError("expected_project_sha256 必须是 64 位小写 SHA-256。")
        actual = self.block_project_sha256()
        if normalized != actual:
            raise ConflictError(f"Block 项目已变化：当前 SHA-256 为 {actual}。")

    def _snapshot_preimage(self, target: Path, data: bytes | None, encoding: str) -> str | None:
        if data is None:
            return None
        snapshot_id = uuid.uuid4().hex
        object_hash = _sha256(data)
        objects = self.root / ".icstex" / "agent-history" / "objects"
        entries = self.root / ".icstex" / "agent-history" / "entries"
        for directory in (objects, entries):
            self._assert_project_file(directory, must_exist=False)
            directory.mkdir(parents=True, exist_ok=True)
        object_path = objects / f"{object_hash}.bin"
        if object_path.exists():
            self._assert_project_file(object_path, must_exist=True)
            if _sha256_file(object_path) != object_hash:
                raise AgentWorkspaceError("历史对象校验失败，已拒绝覆盖。")
        else:
            self._atomic_write_bytes(object_path, data)
        entry = {
            "id": snapshot_id,
            "relativePath": self._relative(target),
            "sha256": object_hash,
            "encoding": encoding,
            "size": len(data),
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        self._atomic_write_bytes(
            entries / f"{snapshot_id}.json",
            (json.dumps(entry, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        return snapshot_id

    def _read_snapshot(self, target: Path, snapshot_id: str) -> tuple[bytes, dict]:
        if not SNAPSHOT_ID_RE.fullmatch(snapshot_id):
            raise UnsafePathError("无效 snapshot id。")
        entry_path = self.root / ".icstex" / "agent-history" / "entries" / f"{snapshot_id}.json"
        self._assert_project_file(entry_path, must_exist=True)
        entry = json.loads(self._read_limited(entry_path, 64 * 1024).decode("utf-8"))
        if entry.get("id") != snapshot_id or entry.get("relativePath") != self._relative(target):
            raise UnsafePathError("snapshot 不属于该文件。")
        object_hash = str(entry.get("sha256", ""))
        if not SHA256_RE.fullmatch(object_hash):
            raise AgentWorkspaceError("snapshot 元数据无效。")
        object_path = self.root / ".icstex" / "agent-history" / "objects" / f"{object_hash}.bin"
        self._assert_project_file(object_path, must_exist=True)
        data = self._read_limited(object_path, MAX_ASSET_BYTES)
        if _sha256(data) != object_hash or len(data) != int(entry.get("size", -1)):
            raise AgentWorkspaceError("snapshot 内容校验失败。")
        return data, entry

    def _snapshot_list(self, target: Path) -> list[dict]:
        entries = self.root / ".icstex" / "agent-history" / "entries"
        if not entries.is_dir() or entries.is_symlink():
            return []
        result: list[dict] = []
        for path in sorted(entries.glob("*.json"), reverse=True):
            if path.is_symlink() or not _is_regular(path):
                continue
            try:
                entry = json.loads(self._read_limited(path, 64 * 1024).decode("utf-8"))
            except (OSError, ValueError, UnicodeError):
                continue
            if entry.get("relativePath") == self._relative(target):
                result.append(entry)
        return sorted(result, key=lambda entry: str(entry.get("createdAt", "")), reverse=True)

    def _remove_snapshot_entry(self, snapshot_id: str) -> None:
        path = self.root / ".icstex" / "agent-history" / "entries" / f"{snapshot_id}.json"
        try:
            self._assert_project_file(path, must_exist=True)
            path.unlink()
        except (OSError, UnsafePathError):
            pass

    def _current_bytes(self, path: Path, limit: int) -> bytes | None:
        if not path.exists():
            return None
        self._assert_project_file(path, must_exist=True)
        if not _is_regular(path):
            raise UnsafePathError(f"不是普通文件：{self._relative(path)}")
        return self._read_limited(path, limit)

    def _atomic_write_bytes(self, path: Path, payload: bytes) -> None:
        self._assert_project_file(path, must_exist=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._assert_project_file(path, must_exist=False)
        original_mode = path.stat().st_mode if path.exists() else None
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if original_mode is not None:
                os.chmod(temporary, stat.S_IMODE(original_mode))
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _read_limited(path: Path, limit: int) -> bytes:
        size = path.stat().st_size
        if size > limit:
            raise AgentWorkspaceError(f"文件超过 {limit} 字节限制。")
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
        if len(data) > limit:
            raise AgentWorkspaceError(f"文件超过 {limit} 字节限制。")
        return data

    @staticmethod
    def _atomic_copy(source: Path, target: Path) -> None:
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, delete=False) as handle:
                temporary = Path(handle.name)
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    # -- query and execution helpers ------------------------------------
    def _search(self, query: str, case_sensitive: bool, whole_word: bool) -> list[dict]:
        if not query:
            return []
        options = SearchOptions(case_sensitive=case_sensitive, whole_word=whole_word)
        results: list[dict] = []
        for path in self._iter_files({".tex", ".bib"}):
            lines = self._read_text(path).splitlines()
            for line_number, text in enumerate(lines, start=1):
                for match in find_matches(text, query, options):
                    results.append(
                        {
                            "file": self._relative(path),
                            "line": line_number,
                            "column": match.start + 1,
                            "excerpt": text.strip()[:500],
                        }
                    )
                    if len(results) >= 500:
                        return results
        return results

    def _iter_files(self, suffixes: set[str]) -> list[Path]:
        files: list[Path] = []
        visited = 0
        for directory, names, filenames in os.walk(self.root, followlinks=False):
            base = Path(directory)
            names[:] = [
                name
                for name in names
                if name not in {".git", ".latex_build", ".icstex", "__pycache__"}
                and not (base / name).is_symlink()
            ]
            for name in filenames:
                visited += 1
                if visited > MAX_PROJECT_FILES:
                    raise AgentWorkspaceError(f"项目文件超过 {MAX_PROJECT_FILES} 个限制。")
                path = base / name
                if path.suffix.lower() in suffixes and not path.is_symlink() and _is_regular(path):
                    files.append(path)
        return sorted(files)

    def _combined_tex_text(self, root_file: Path) -> str:
        parts: list[str] = []
        for path in sorted(self._safe_tex_closure(root_file)):
            parts.append(self._read_text(path))
        return "\n".join(parts)

    def _combined_bib_text(self) -> str:
        return "\n".join(self._read_text(path) for path in self._iter_files({".bib"}))

    def _read_text(self, path: Path) -> str:
        return decode_latex_bytes(self._read_limited(path, MAX_TEXT_BYTES)).text

    def _source_state(self, record: SourceRecord) -> dict:
        result = record.to_dict()
        try:
            path = self._project_path(record.relativePath, must_exist=False)
            if not path.exists():
                result["state"] = "missing"
            elif not _is_regular(path):
                result["state"] = "unsafe"
            else:
                current = _sha256_file(path)
                result["currentSha256"] = current
                result["state"] = "ok" if current == record.baseSha256 else "changed"
        except UnsafePathError:
            result["state"] = "unsafe"
        return result

    def _diagnostic(self, diagnostic: object) -> dict:
        data = _plain(diagnostic)
        file_value = data.get("file") if isinstance(data, dict) else None
        if file_value:
            try:
                path = Path(str(file_value)).resolve()
                data["file"] = self._relative(path) if path.is_relative_to(self.root) else "<outside-project>"
            except OSError:
                data["file"] = "<unavailable>"
        return data

    def _sync_position(self, position: object | None) -> dict | None:
        if position is None:
            return None
        data = _plain(position)
        path = Path(str(data["file"])).resolve()
        if not path.is_relative_to(self.root):
            raise UnsafePathError("SyncTeX 返回了项目外路径。")
        self._assert_project_file(path, must_exist=True)
        data["file"] = self._relative(path)
        return data

    def _compile_result(self, result: CompileResult) -> dict:
        return {
            "ok": result.ok,
            "outcome": result.outcome.value,
            "purpose": result.purpose.value,
            "buildId": result.build_id,
            "durationSeconds": result.duration_seconds,
            "returncode": result.returncode,
            "rootFile": self._relative(result.root_file),
            "pdfFile": self._relative(result.pdf_file),
            "logFile": self._relative(result.log_file),
            "command": [Path(item).name if index == 0 else self._redact_command_item(item) for index, item in enumerate(result.command)],
            "stdoutTail": result.stdout[-4000:],
            "stderrTail": result.stderr[-4000:],
            "errors": [self._latex_error(error) for error in result.errors],
            "previewFidelity": result.preview_fidelity,
        }

    def _latex_error(self, error: object) -> dict:
        data = _plain(error)
        file_value = data.get("file") if isinstance(data, dict) else None
        if file_value:
            path = Path(str(file_value)).resolve()
            data["file"] = self._relative(path) if path.is_relative_to(self.root) else "<outside-project>"
        return data

    def _redact_command_item(self, item: str) -> str:
        item = item.replace(str(self.root), "<project>")
        try:
            path = Path(item).expanduser().resolve()
        except (OSError, RuntimeError):
            return item
        return self._relative(path) if path.is_relative_to(self.root) else item

    def _recognize_formula(self, image: Path, temperature: float) -> dict:
        from app.optional_tools.pix2tex.environment import manifest_path, python_executable

        python = python_executable()
        manifest = manifest_path()
        if not python.is_file() or not manifest.is_file():
            raise AgentWorkspaceError("pix2tex 本地运行时或模型未安装。")
        request_id = f"mcp-{uuid.uuid4().hex[:12]}"
        messages = [
            {"id": request_id, "method": "recognize", "params": {"image_path": str(image)}},
            {"id": None, "method": "shutdown"},
        ]
        output = self._run_worker(
            [str(python), "-m", "app.optional_tools.pix2tex.worker_entry", "--manifest", str(manifest), "--temperature", str(temperature)],
            messages,
            timeout=210,
        )
        for message in output:
            if message.get("id") == request_id and "result" in message:
                return dict(message["result"])
            if "error" in message:
                error = message["error"]
                raise AgentWorkspaceError(f"pix2tex {error.get('code', 'ERROR')}: {error.get('message', '')}")
        raise AgentWorkspaceError("pix2tex 未返回识别结果。")

    def _recognize_text(self, image: Path) -> dict:
        from app.services.recognition.runtime_manager import provider_python

        python = provider_python("rapidocr")
        if not python.is_file():
            raise AgentWorkspaceError("RapidOCR 本地运行时未安装。")
        request_id = f"mcp-{uuid.uuid4().hex[:12]}"
        messages = [
            {"action": "recognize", "requestId": request_id, "kind": "text", "imagePath": str(image)},
            {"action": "shutdown", "requestId": None},
        ]
        output = self._run_worker(
            [str(python), "-m", "app.services.recognition.worker_entry", "--kind", "text"],
            messages,
            timeout=60,
        )
        for message in output:
            if message.get("requestId") == request_id:
                if message.get("ok"):
                    return message
                error = message.get("error", {})
                raise AgentWorkspaceError(f"RapidOCR {error.get('code', 'ERROR')}: {error.get('message', '')}")
        raise AgentWorkspaceError("RapidOCR 未返回识别结果。")

    def _run_worker(self, command: list[str], messages: list[dict], *, timeout: float) -> list[dict]:
        environment = os.environ.copy()
        package_root = str(Path(__file__).resolve().parents[2])
        existing = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join(part for part in (package_root, existing) if part)
        kwargs: dict[str, object] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "env": environment,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(command, **kwargs)
        payload = "".join(json.dumps(message) + "\n" for message in messages)
        try:
            stdout, stderr = process.communicate(payload, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            CompileManager._terminate_process(process)
            process.communicate()
            raise AgentWorkspaceError("本地识别超时，进程已终止。") from exc
        if len(stdout.encode("utf-8", errors="replace")) > MAX_WORKER_OUTPUT_BYTES:
            raise AgentWorkspaceError("本地识别响应过大。")
        parsed: list[dict] = []
        for line in stdout.splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                parsed.append(value)
        if process.returncode not in (0, None) and not parsed:
            raise AgentWorkspaceError("本地识别进程失败：" + stderr[-1000:])
        return parsed

    # -- small helpers ---------------------------------------------------
    def _require(self, capability: str) -> None:
        enabled = {
            "write": self.grants.allow_write,
            "compile": self.grants.allow_compile,
            "network": self.grants.allow_network,
            "recognition": self.grants.allow_recognition,
        }[capability]
        if not enabled:
            raise CapabilityDenied(f"未授予 {capability} 能力；必须由 MCP 宿主在启动时显式授权。")

    def _relative(self, path: Path) -> str:
        return path.resolve(strict=False).relative_to(self.root).as_posix()

    def _relative_or_none(self, path: Path | None) -> str | None:
        if path is None:
            return None
        try:
            self._assert_project_file(path, must_exist=True)
            return self._relative(path)
        except (AgentWorkspaceError, ValueError, OSError):
            return None


def _canonical_directory(path: str | Path, *, label: str) -> Path:
    lexical = Path(os.path.abspath(Path(path).expanduser()))
    if not lexical.exists() or not lexical.is_dir() or lexical.is_symlink():
        raise UnsafePathError(f"{label} 必须是存在的非符号链接目录：{lexical}")
    return lexical.resolve(strict=True)


def _canonical_input(path: str | Path) -> Path:
    lexical = Path(os.path.abspath(Path(path).expanduser()))
    if not lexical.exists() or lexical.is_symlink():
        raise UnsafePathError(f"输入授权不存在或是符号链接：{lexical}")
    canonical = lexical.resolve(strict=True)
    if not (canonical.is_dir() or _is_regular(canonical)):
        raise UnsafePathError(f"输入授权必须是普通文件或目录：{lexical}")
    return canonical


def _safe_relative_parts(value: str) -> tuple[str, ...]:
    raw = str(value).strip()
    if not raw or "\x00" in raw or "\\" in raw or "://" in raw:
        raise UnsafePathError("必须提供 POSIX 风格项目相对路径。")
    if raw.startswith("/") or any(part in {"", ".", ".."} for part in raw.split("/")):
        raise UnsafePathError("拒绝绝对路径、空路径段、. 或 ..。")
    candidate = PurePosixPath(raw)
    if candidate.is_absolute() or not candidate.parts:
        raise UnsafePathError("必须提供项目相对路径。")
    if len(candidate.parts[0]) == 2 and candidate.parts[0][1] == ":":
        raise UnsafePathError("拒绝 Windows 盘符路径。")
    return tuple(candidate.parts)


def _is_regular(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.stat(follow_symlinks=False).st_mode)
    except OSError:
        return False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _plain(value: object) -> object:
    if is_dataclass(value):
        return _plain(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(item) for item in value]
    return value


def _lock_handle(handle: object) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)  # type: ignore[attr-defined]
        if handle.read(1) == b"":  # type: ignore[attr-defined]
            handle.write(b"\0")  # type: ignore[attr-defined]
            handle.flush()  # type: ignore[attr-defined]
        handle.seek(0)  # type: ignore[attr-defined]
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)  # type: ignore[attr-defined]
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)  # type: ignore[attr-defined]


def _unlock_handle(handle: object) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)  # type: ignore[attr-defined]
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
