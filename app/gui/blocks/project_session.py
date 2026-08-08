"""Single project state shared by the Block workspace and the main console.

One ``ProjectSession`` owns the registry, layout, sources, themes, table
model, the single ``CompileManager``, the global ``QUndoStack`` and the
``SelectionManager``.  All GUI components receive the same session object;
no component loads its own project copy or starts its own compiler.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QUndoStack

from app.core.blocks.block_renderer import RenderPolicy, render_block, required_packages_for_block
from app.core.blocks.layout import LayoutNode
from app.core.blocks.layout_renderer import render_layout
from app.core.blocks.layout_solver import solve_layout
from app.core.blocks.project_repository import save_project
from app.core.blocks.registry import BlockRegistry
from app.core.blocks.source_registry import SourceRecord
from app.core.blocks.table_model import TableData, TableEditorModel
from app.core.blocks.theme import AppTheme, DocumentTheme
from app.core.blocks.theme_renderer import render_document_theme_sty
from app.core.compiler import BuildPurpose, CompileManager
from app.core.latex_tools import LaTeXEngine, detect_toolchain
from app.gui.blocks import profile
from app.gui.blocks.selection import SelectionManager


_SAVE_DEBOUNCE_MS = 500
_PREVIEW_DEBOUNCE_MS = 700
_COMPILE_TIMEOUT_SECONDS = 300


class ProjectSession(QObject):
    """The only project state object in the Block console integration."""

    model_changed = Signal(str)
    save_requested = Signal(str)
    save_completed = Signal(str)
    compile_requested = Signal(str)
    compile_finished = Signal(object)

    def __init__(
        self,
        *,
        registry: BlockRegistry | None = None,
        layout: LayoutNode | None = None,
        sources: list[SourceRecord] | tuple[SourceRecord, ...] | None = None,
        document_theme: DocumentTheme | None = None,
        app_theme: AppTheme | None = None,
        project_dir: Path | str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.registry = registry if registry is not None else BlockRegistry()
        self.layout = layout
        self.sources: list[SourceRecord] = list(sources or [])
        self.document_theme = document_theme or DocumentTheme(id="doc_default", name="Default")
        self.app_theme = app_theme
        self.project_dir = Path(project_dir).expanduser().resolve() if project_dir else None
        self.table_model = TableEditorModel(TableData())
        self.ensure_table_model()
        self.undo_stack = QUndoStack(self)
        self.selection = SelectionManager(self)
        self.compile_manager: CompileManager | None = None
        self._compile_launches = 0
        self._revision = 0
        self._last_assemble_stats: dict = {}
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(_SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self.save_now)
        self._pending_save_reason = ""
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(_PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._fire_preview)

    # --- identity helpers (Phase 2 acceptance) ---------------------------
    def core_objects(self) -> dict:
        """Return the shared model objects; identity tests assert these are the
        exact instances every GUI component uses."""
        return {
            "registry": self.registry,
            "layout": self.layout,
            "sources": self.sources,
            "document_theme": self.document_theme,
            "table_model": self.table_model,
            "compile_manager": self.compile_manager,
            "undo_stack": self.undo_stack,
            "selection": self.selection,
        }

    def next_alias(self, block_type: str) -> str:
        existing = {block.alias for block in self.registry.blocks()}
        index = 1
        while f"{block_type}_{index}" in existing:
            index += 1
        return f"{block_type}_{index}"

    def ensure_table_model(self) -> TableEditorModel:
        """Initialize the shared table model from the table block when empty."""
        table_block = next((block for block in self.registry.blocks() if block.type == "table"), None)
        if table_block is not None and not self.table_model.data.columns and not self.table_model.data.rows:
            try:
                self.table_model = TableEditorModel(TableData.from_content_dict(table_block.content))
            except (ValueError, KeyError, TypeError):
                pass
        return self.table_model

    # --- model change routing --------------------------------------------
    def set_layout(self, layout: LayoutNode | None, *, reason: str = "layout_changed") -> None:
        self.layout = layout
        self.notify_model_changed(reason)

    def sync_table_to_registry(self) -> None:
        table_block = next((block for block in self.registry.blocks() if block.type == "table"), None)
        if table_block is not None:
            self.registry.update(table_block.id, {"content": self.table_model.data.to_content_dict()})

    def table_edited(self) -> None:
        self.sync_table_to_registry()

    def notify_model_changed(self, reason: str) -> None:
        """Single routing point: one model change -> one save + one preview."""
        self._revision = profile.new_revision()
        table_block = next((b for b in self.registry.blocks() if b.type == "table"), None)
        profile.log(
            "MODEL_CHANGED",
            revision=self._revision,
            reason=reason,
            blocks=len(self.registry.blocks()),
            layout_nodes=_count_layout_nodes(self.layout),
            table_rows=len(self.table_model.data.rows) if table_block else 0,
            table_cols=len(self.table_model.data.columns) if table_block else 0,
        )
        self.model_changed.emit(reason)
        self.request_save(reason)
        self.request_preview(reason)

    # --- unified save ----------------------------------------------------
    def request_save(self, reason: str) -> None:
        self._pending_save_reason = reason
        profile.log("SAVE_REQUESTED", revision=self._revision, reason=reason)
        self.save_requested.emit(reason)
        if self.project_dir is not None:
            self._save_timer.start()

    def save_now(self) -> list[Path]:
        self._save_timer.stop()
        if self.project_dir is None:
            return []
        watch = profile.Stopwatch()
        profile.log("SAVE_STARTED", revision=self._revision)
        self.sync_table_to_registry()
        written = save_project(
            self.project_dir,
            registry=self.registry,
            layout=self.layout,
            sources=self.sources,
            document_theme=self.document_theme,
        )
        bytes_written = sum(path.stat().st_size for path in written if path.exists())
        profile.log(
            "SAVE_FINISHED",
            revision=self._revision,
            files_written=len(written),
            bytes_written=bytes_written,
            elapsed_ms=round(watch.elapsed_ms(), 2),
        )
        self.save_completed.emit(self._pending_save_reason)
        return written

    # --- unified compile routing ----------------------------------------
    def assemble_latex(self) -> Path | None:
        """Deterministic Stable LaTeX regeneration (same output as the MVP)."""
        if self.project_dir is None:
            return None
        project = self.project_dir
        watch = profile.Stopwatch()
        stats = {"considered": 0, "written": 0, "unchanged": 0, "bytes_written": 0}
        self.sync_table_to_registry()
        blocks_dir = project / "blocks"
        blocks_dir.mkdir(parents=True, exist_ok=True)
        block_latex: dict[str, str] = {}
        for block in self.registry.blocks():
            latex = render_block(
                block,
                in_box=True,
                policy=RenderPolicy(
                    allow_trusted_raw_latex=getattr(self, "_raw_latex_authorized", False),
                    project_root=project,
                ),
            )
            path = blocks_dir / f"{block.id}.tex"
            stats["considered"] += 1
            if _write_if_changed(path, latex):
                stats["written"] += 1
                stats["bytes_written"] += len(latex.encode("utf-8"))
            else:
                stats["unchanged"] += 1
            block_latex[block.id] = f"\\input{{blocks/{block.id}.tex}}\n"
        body = render_layout(solve_layout(self.layout, 426.0), block_latex) if self.layout is not None else ""
        packages = sorted(
            {"graphicx"}
            | {package for block in self.registry.blocks() for package in required_packages_for_block(block, in_box=True)}
        )
        styles = project / "styles"
        styles.mkdir(parents=True, exist_ok=True)
        sty = render_document_theme_sty(self.document_theme)
        sty_path = styles / "icstex-generated.sty"
        stats["considered"] += 1
        if _write_if_changed(sty_path, sty):
            stats["written"] += 1
            stats["bytes_written"] += len(sty.encode("utf-8"))
        else:
            stats["unchanged"] += 1
        main = project / "main.tex"
        main_text = (
            "\\documentclass{ctexart}\n"
            + "".join(f"\\usepackage{{{package}}}\n" for package in packages)
            + "\\input{styles/icstex-generated.sty}\n"
            + "\\graphicspath{{assets/images/}}\n"
            + "\\begin{document}\n"
            + body
            + "\\end{document}\n"
        )
        stats["considered"] += 1
        if _write_if_changed(main, main_text):
            stats["written"] += 1
            stats["bytes_written"] += len(main_text.encode("utf-8"))
        else:
            stats["unchanged"] += 1
        self._last_assemble_stats = stats
        profile.log(
            "ASSEMBLE_FINISHED",
            revision=self._revision,
            blocks=len(self.registry.blocks()),
            files_considered=stats["considered"],
            files_written=stats["written"],
            files_unchanged=stats["unchanged"],
            bytes_written=stats["bytes_written"],
            elapsed_ms=round(watch.elapsed_ms(), 2),
        )
        return main

    def request_preview(self, reason: str) -> None:
        """Debounced, single-process PREVIEW compile through one CompileManager."""
        profile.log("COMPILE_REQUESTED", revision=self._revision, reason=reason)
        self.compile_requested.emit(reason)
        if self.project_dir is None:
            return
        profile.log(
            "COMPILE_DEBOUNCE_STARTED",
            revision=self._revision,
            debounce_ms=_PREVIEW_DEBOUNCE_MS,
        )
        # Stable LaTeX generation is deferred into the debounce so the per-edit
        # hot path stays cheap; a single assemble + one latex process follows.
        self._preview_timer.start()

    def _fire_preview(self) -> None:
        if self.project_dir is None:
            return
        main = self.assemble_latex()
        if main is None:
            return
        self._ensure_compile_manager(main)
        self.compile_manager.compile_async(BuildPurpose.PREVIEW)

    def compile_final(self) -> object:
        """Synchronous FINAL compile (the console's '生成并编译 PDF' button)."""
        self._preview_timer.stop()
        if self.project_dir is None:
            return None
        self._raw_latex_authorized = True
        main = self.assemble_latex()
        if main is None:
            return None
        self._ensure_compile_manager(main)
        result = self.compile_manager.compile_now(
            BuildPurpose.FINAL,
            timeout_seconds=_COMPILE_TIMEOUT_SECONDS,
        )
        if result is not None:
            self.compile_finished.emit(result)
        return result

    def _ensure_compile_manager(self, main: Path) -> None:
        if self.compile_manager is None:
            self.compile_manager = CompileManager(
                main,
                toolchain=detect_toolchain(),
                engine=LaTeXEngine.XELATEX,
                on_started=self._on_compile_started,
                on_finished=self._on_compile_finished,
            )

    def _on_compile_started(self, root_file, build_id: int) -> None:
        self._compile_launches += 1
        profile.log(
            "LATEX_PROCESS_STARTED",
            revision=self._revision,
            build_id=build_id,
            launches=self._compile_launches,
        )

    def _on_compile_finished(self, result: object) -> None:
        profile.log(
            "LATEX_PROCESS_EXITED",
            revision=self._revision,
            launches=self._compile_launches,
            outcome=getattr(getattr(result, "outcome", None), "value", None),
        )
        self.compile_finished.emit(result)

    def stop_compile(self) -> None:
        self._preview_timer.stop()
        if self.compile_manager is not None:
            self.compile_manager.stop_current(timeout=1.0)
            # Late worker results must never emit on a closed session.
            self.compile_manager.on_finished = None


def _count_layout_nodes(layout) -> int:
    if layout is None:
        return 0
    if not hasattr(layout, "kind"):
        return 1
    return 1 + sum(_count_layout_nodes(child) for child in layout.children)


def _write_if_changed(path: Path, text: str) -> bool:
    """Write only when the content changed; returns True when written."""
    new_bytes = text.encode("utf-8")
    try:
        if path.exists() and path.read_bytes() == new_bytes:
            return False
    except OSError:
        pass
    path.write_text(text, encoding="utf-8")
    return True
