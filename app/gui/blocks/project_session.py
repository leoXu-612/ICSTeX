"""Single project state shared by the Block workspace and the main console.

One ``ProjectSession`` owns the registry, layout, sources, themes, table
model, the single ``CompileManager``, the global ``QUndoStack`` and the
``SelectionManager``.  All GUI components receive the same session object;
no component loads its own project copy or starts its own compiler.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QUndoStack

from app.core.blocks.assembly import build_latex_files
from app.core.blocks.layout import LayoutNode
from app.core.blocks.project_repository import project_payloads
from app.core.blocks.project_write import BlockWriteGuard
from app.core.blocks.property_draft import PropertyDraft, draft_conflict, prepare_drafts, table_projection
from app.core.blocks.registry import BlockRegistry
from app.core.blocks.schema import validate_block
from app.core.blocks.source_registry import SourceRecord
from app.core.blocks.table_model import TableData, TableEditorModel
from app.core.blocks.theme import AppTheme, DocumentTheme
from app.core.compiler import BuildPurpose, CompileManager
from app.core.build_evidence import final_build_evidence
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
    save_state_changed = Signal()
    editor_drafts_changed = Signal()
    finish_editor_inputs = Signal()
    compile_requested = Signal(str)
    compile_finished = Signal(object)
    compile_state_changed = Signal()
    _job_started = Signal(object, int)
    _job_finished = Signal(object)

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
        self._empty_table_model = TableEditorModel(TableData())
        self.table_model = self._empty_table_model
        self.table_target_id = None
        self._table_editors = {}
        self._table_model_source_valid = False
        self.table_error = "请选择要编辑的表格。"
        self.undo_stack = QUndoStack(self)
        self.selection = SelectionManager(self)
        self.compile_manager: CompileManager | None = None
        self._compile_launches = 0
        self._revision = 0
        self._closed = False
        self._compile_authorized = False
        self._writes_paused = False
        self._checkpoint_paused = False
        self._dirty = False
        self.editor_drafts: dict[tuple[str, str], PropertyDraft] = {}
        self.editor_draft_revision = 0
        self.editor_draft_error = ""
        self.save_error = ""
        self.last_save_ok = False
        self._latest_build_id = 0
        self._accepted_build_id = 0
        self.final_evidence = None
        self.last_result = None
        self.final_is_running = False
        self.compile_generation = 0
        self._job_started.connect(self._accept_compile_started)
        self._job_finished.connect(self._accept_compile_result)
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
        self._write_guard = None
        self._new_destination = self.project_dir is not None and not self.project_dir.exists()
        self._initial_metadata = self._initial_generated = self._initial_trusted = None
        try:
            self._initial_metadata = self._metadata()
            self._initial_generated = self._generated()
            self._initial_trusted = self._generated(trusted=True)
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            # Incomplete in-memory editor drafts may still be displayed. They
            # are not permission to replace a persisted or unknown model.
            self.save_error = f"模型尚不能安全保存，原始内容保留：{exc}"
        self._dirty = bool(self.registry.blocks() or self.layout or self.sources) and (
            self.project_dir is None or not (self.project_dir / ".icstex/blocks.json").exists())
        if self.project_dir is not None and not self._new_destination:
            try:
                self._capture_writer()
            except (OSError, ValueError, RecursionError) as exc:
                self.save_error = f"当前 Block 文件不能安全覆盖：{exc}"
        tables = [block for block in self.registry.blocks() if block.type == "table"]
        if len(tables) == 1:
            self.table_target_id = tables[0].id
        self.ensure_table_model()

    @property
    def has_unsaved_changes(self) -> bool:
        return self._dirty or bool(self.editor_drafts)

    def set_editor_draft(self, draft: PropertyDraft) -> None:
        if self._closed:
            return
        previous = self.editor_drafts.get(draft.key)
        if draft.changed:
            if previous == draft:
                return
            self.editor_drafts[draft.key] = draft
        elif previous is not None:
            del self.editor_drafts[draft.key]
        else:
            return
        self._editor_drafts_updated()

    def discard_editor_draft(self, key) -> None:
        if not self._closed and self.editor_drafts.pop(key, None) is not None:
            self._editor_drafts_updated()

    def _editor_drafts_updated(self):
        self.editor_draft_revision += 1
        self.editor_draft_error = ""
        if self.editor_drafts:
            self._save_timer.stop()
            self._preview_timer.stop()
        elif self._dirty and self.project_dir is not None and not self._writes_paused and not self.save_error:
            # The model change already issued its single save/preview request.
            # Resume those timers without broadcasting a second request.
            self._save_timer.start()
            if self._compile_authorized:
                self._preview_timer.start()
        self.editor_drafts_changed.emit()
        self.save_state_changed.emit()

    def apply_editor_drafts(self, keys=None) -> bool:
        if self._closed:
            return False
        self.finish_editor_inputs.emit()
        selected = tuple(self.editor_drafts.values()) if keys is None else tuple(
            self.editor_drafts[key] for key in keys if key in self.editor_drafts)
        if not selected:
            return True
        try:
            patches, layout = prepare_drafts(selected, self.registry, self.layout)
        except ValueError as exc:
            self.editor_draft_error = str(exc)
            self.editor_drafts_changed.emit()
            return False
        from app.gui.blocks.commands import ApplyPropertyDraftsCommand
        if patches or layout != self.layout:
            self.undo_stack.push(ApplyPropertyDraftsCommand(self, patches, layout))
        for draft in selected:
            # Model notifications can re-enter an editor; never erase newer input.
            if self.editor_drafts.get(draft.key) == draft:
                del self.editor_drafts[draft.key]
        self._editor_drafts_updated()
        return True

    def _metadata(self):
        return project_payloads(self.project_dir or Path("."), registry=self.registry,
                                layout=self.layout, sources=self.sources, document_theme=self.document_theme)

    def _generated(self, *, trusted=None):
        files = build_latex_files(self.project_dir or Path("."), registry=self.registry, layout=self.layout,
                                 document_theme=self.document_theme,
                                 allow_trusted_raw_latex=(getattr(self, "_raw_latex_authorized", False)
                                                        if trusted is None else trusted))
        return {path: text.encode("utf-8") for path, text in files.items()}

    def _capture_writer(self):
        if self._initial_metadata is None or self._initial_generated is None:
            raise ValueError("Cannot establish original Block model ownership")
        self._write_guard = BlockWriteGuard(self.project_dir, self._initial_metadata, self._initial_generated,
                                           generated_alternative=self._initial_trusted)

    def _writer(self):
        if self._write_guard is None:
            if self._new_destination:
                if self._initial_metadata is None:
                    self._initial_metadata = self._metadata()
                    self._initial_generated = self._generated()
                    self._initial_trusted = self._generated(trusted=True)
                # Reserve only the explicitly selected NEW destination. Never
                # adopt a directory created by someone else after selection.
                self.project_dir.mkdir(mode=0o700, exist_ok=False)
                self._new_destination = False
            self._capture_writer()
        return self._write_guard

    def bind_new_project(self, path: Path) -> None:
        if self.project_dir is not None:
            raise ValueError("Existing Block projects cannot silently change destination")
        parent = path.parent.expanduser().resolve(strict=True)
        target = parent / path.name
        if target.exists() or target.is_symlink():
            raise FileExistsError("请选择尚不存在的新项目目录。")
        self.project_dir = target
        self._new_destination = True
        self._initial_metadata = self._metadata()
        self._initial_generated = self._generated()
        self._initial_trusted = self._generated(trusted=True)
        self.save_error = ""

    def pause_writes(self):
        pending = self._save_timer.isActive(), self._preview_timer.isActive()
        self._writes_paused = True
        self._save_timer.stop()
        self._preview_timer.stop()
        return pending

    def resume_writes(self, pending):
        self._writes_paused = False
        if self._closed or self.save_error or self.editor_drafts:
            return
        if pending[0] and self._dirty:
            self._save_timer.start()
        if pending[1] and self._compile_authorized:
            self._preview_timer.start()

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

    def ensure_table_model(self, block_id=None) -> TableEditorModel:
        """Project the explicit target; retain local Undo only for pending drafts."""
        if block_id is not None:
            self.table_target_id = block_id
        target = self.table_target_id
        draft = self.editor_drafts.get(("table", target))
        block = self.registry.get(target) if target else None
        base = draft.base if draft else (block.to_dict() if block is not None and block.type == "table" else None)
        self.table_model = self._empty_table_model
        self._table_model_source_valid = False
        self.table_error = "请选择要编辑的表格。" if target is None else "表格已删除或类型已改变；不会改写其他表格。"
        if base is not None:
            try:
                if validate_block(base):
                    raise ValueError("未知表格格式，原内容保留。")
                initial = table_projection(base["content"])
                values = draft.values if draft else initial
                cached = self._table_editors.get(target)
                if (cached is None or cached[0].base != base
                        or cached[1].data.to_content_dict() != values):
                    template = PropertyDraft("table", target, f"表格 {base['alias']}",
                                             deepcopy(base), initial, initial)
                    cached = template, TableEditorModel(TableData.from_content_dict(values))
                    self._table_editors[target] = cached
                self.table_model = cached[1]
                self._table_model_source_valid = True
                self.table_error = draft_conflict(draft, self.registry, self.layout) if draft else ""
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                self.table_error = f"表格不能安全编辑，原内容保留：{exc}"
        for key in tuple(self._table_editors):
            if key != target and ("table", key) not in self.editor_drafts:
                del self._table_editors[key]
        return self.table_model

    def table_edited(self, block_id=None, model=None) -> None:
        target = block_id if block_id is not None else self.table_target_id
        cached = self._table_editors.get(target)
        if self._closed or cached is None or (model is not None and cached[1] is not model):
            return
        template, model = cached
        self.set_editor_draft(replace(template, values=model.data.to_content_dict()))

    def table_cell_edited(self, block_id, payload):
        key = ("table_cell", block_id)
        if payload is None:
            self.discard_editor_draft(key)
            return
        cached = self._table_editors.get(block_id)
        if self._closed or cached is None:
            return
        template, _model = cached
        initial = {"row": payload["row"], "column": payload["column"], "text": payload["initial"]}
        self.set_editor_draft(PropertyDraft("table_cell", block_id, f"{template.label} · 正在编辑单元格",
            template.base, initial, {**initial, "text": payload["text"]}))

    def seed_table_draft(self, model, block_id=None) -> None:
        """Compatibility input is an explicit-target draft, never saved implicitly."""
        if block_id is None:
            tables = [block for block in self.registry.blocks() if block.type == "table"]
            if len(tables) != 1:
                raise ValueError("外部表格草稿必须指定唯一的目标 Block。")
            block_id = tables[0].id
        self.ensure_table_model(block_id)
        if not self._table_model_source_valid:
            raise ValueError(self.table_error)
        template, _old = self._table_editors[block_id]
        self._table_editors[block_id] = template, model
        self.table_model = model
        self.table_edited()

    # --- model change routing --------------------------------------------
    def set_layout(self, layout: LayoutNode | None, *, reason: str = "layout_changed") -> None:
        self.layout = layout
        self.notify_model_changed(reason)

    def notify_model_changed(self, reason: str) -> None:
        """Single routing point: one model change -> one save + one preview."""
        if self._closed:
            return
        self._dirty = True
        self._revision = profile.new_revision()
        table_block = self.registry.get(self.table_target_id) if self.table_target_id else None
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
        if self._closed:
            return
        self._pending_save_reason = reason
        profile.log("SAVE_REQUESTED", revision=self._revision, reason=reason)
        self.save_requested.emit(reason)
        if self.project_dir is not None and not self.save_error and not self._writes_paused and not self.editor_drafts:
            self._save_timer.start()

    def save_now(self) -> list[Path]:
        self._save_timer.stop()
        self.last_save_ok = False
        if self._closed or self._checkpoint_paused or self.project_dir is None or self.editor_drafts:
            return []
        watch = profile.Stopwatch()
        profile.log("SAVE_STARTED", revision=self._revision)
        try:
            # Persist one model/generation version even before the first compile.
            # Otherwise a clean reopen cannot distinguish stale generated TeX
            # from an external edit and must refuse all subsequent writes.
            payloads = {**self._metadata(), **self._generated()}
            written = self._writer().write(payloads)
        except (OSError, ValueError, RecursionError) as exc:
            self._save_failed(exc)
            return []
        self._dirty = False
        self.save_error = ""
        self.last_save_ok = True
        bytes_written = sum(len(payloads[path]) for path in written)
        profile.log(
            "SAVE_FINISHED",
            revision=self._revision,
            files_written=len(written),
            bytes_written=bytes_written,
            elapsed_ms=round(watch.elapsed_ms(), 2),
        )
        self.save_completed.emit(self._pending_save_reason)
        self.save_state_changed.emit()
        return written

    def _save_failed(self, error):
        self.last_save_ok = False
        self._save_timer.stop()
        self._preview_timer.stop()
        self.save_error = f"未保存，内存草稿与外部文件均保留；自动保存/预览已暂停。{error}"
        self.save_state_changed.emit()

    # --- unified compile routing ----------------------------------------
    def assemble_latex(self) -> Path | None:
        """Deterministic Stable LaTeX regeneration (same output as the MVP)."""
        if self._closed or self._checkpoint_paused or self.project_dir is None or self.editor_drafts:
            return None
        project = self.project_dir
        watch = profile.Stopwatch()
        stats = {"considered": 0, "written": 0, "unchanged": 0, "bytes_written": 0}
        try:
            generated = self._generated()
            written = self._writer().write({**self._metadata(), **generated})
        except (OSError, ValueError, RecursionError) as exc:
            self._save_failed(exc)
            return None
        self._dirty = False
        self.save_error = ""
        self.last_save_ok = True
        self._save_timer.stop()
        self.save_completed.emit(self._pending_save_reason)
        self.save_state_changed.emit()
        stats["considered"] = len(generated)
        stats["written"] = sum(path in generated for path in written)
        stats["bytes_written"] = sum(len(generated[path]) for path in written if path in generated)
        stats["unchanged"] = len(generated) - stats["written"]
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
        return project / "main.tex"

    def request_preview(self, reason: str) -> None:
        """Debounced, single-process PREVIEW compile through one CompileManager."""
        if self._closed:
            return
        profile.log("COMPILE_REQUESTED", revision=self._revision, reason=reason)
        self.compile_requested.emit(reason)
        if (self.project_dir is None or not self._compile_authorized
                or self.save_error or self._writes_paused or self.editor_drafts):
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
        if (self._closed or self.project_dir is None or not self._compile_authorized
                or self._writes_paused or self.save_error or self.editor_drafts):
            return
        main = self.assemble_latex()
        if main is None:
            return
        self._ensure_compile_manager(main)
        self.compile_manager.set_input_revision(self._revision)
        self.compile_manager.compile_async(BuildPurpose.PREVIEW)

    def compile_final(self) -> object:
        """Synchronous compatibility/probe entry; the visible UI uses request_final."""
        if not self._prepare_final():
            return None
        return self.compile_manager.compile_now(BuildPurpose.FINAL, timeout_seconds=_COMPILE_TIMEOUT_SECONDS)

    @Slot()
    def request_final(self) -> None:
        if self._prepare_final():
            self.compile_manager.compile_async(BuildPurpose.FINAL)
            self.compile_state_changed.emit()

    def _prepare_final(self) -> bool:
        self._preview_timer.stop()
        if self._closed or self._checkpoint_paused or self.project_dir is None or self.editor_drafts:
            return False
        self._raw_latex_authorized = True
        self._compile_authorized = True
        main = self.assemble_latex()
        if main is None:
            return False
        self._ensure_compile_manager(main)
        self.compile_manager.set_input_revision(self._revision)
        return True

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
        self._job_started.emit(self.compile_manager.active_job_key, build_id)

    def _on_compile_finished(self, result: object) -> None:
        profile.log(
            "LATEX_PROCESS_EXITED",
            revision=self._revision,
            launches=self._compile_launches,
            outcome=getattr(getattr(result, "outcome", None), "value", None),
        )
        self._job_finished.emit(result)

    @Slot(object, int)
    def _accept_compile_started(self, job_key, build_id: int) -> None:
        if self._closed or job_key is None or not self.project_dir or job_key.root_file != self.project_dir / "main.tex":
            return
        if build_id <= self._latest_build_id:
            return
        self._latest_build_id = build_id
        self.final_is_running = job_key.purpose is BuildPurpose.FINAL
        self.compile_generation += 1
        self.compile_state_changed.emit()

    @Slot(object)
    def _accept_compile_result(self, result) -> None:
        if (self._closed or result.build_id != self._latest_build_id
                or result.build_id <= self._accepted_build_id):
            return
        self._accepted_build_id = result.build_id
        self.last_result = result
        self.final_is_running = False
        evidence = final_build_evidence(result)
        if evidence is not None:
            self.final_evidence = evidence
        self.compile_generation += 1
        self.compile_state_changed.emit()
        self.compile_finished.emit(result)

    def stop_compile(self) -> None:
        self.final_is_running = False
        self._preview_timer.stop()
        if self.compile_manager is not None:
            self.compile_manager.stop_current(timeout=1.0)
        self.compile_state_changed.emit()

    def shutdown(self) -> None:
        """Called only after the close choice; prevents all late writes/results."""
        self._closed = True
        self._save_timer.stop()
        self.stop_compile()
        if self.compile_manager is not None:
            # Late worker results must never emit on a closed session.
            self.compile_manager.on_finished = None


def _count_layout_nodes(layout) -> int:
    if layout is None:
        return 0
    if not hasattr(layout, "kind"):
        return 1
    return 1 + sum(_count_layout_nodes(child) for child in layout.children)
