"""Lightweight wrapper around the reusable Block workspace.

The dialog no longer owns project state or a compiler: it builds (or accepts)
one ``ProjectSession`` and delegates everything to the session + workspace +
controller.  The constructor keeps the legacy signature so existing tests and
the standalone debugging entry keep working.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QVBoxLayout

from app.core.blocks.registry import BlockRegistry
from app.core.blocks.source_merge import MergeResult
from app.core.blocks.table_model import TableData, TableEditorModel
from app.core.blocks.theme import AppTheme, DocumentTheme
from app.gui.blocks.project_session import ProjectSession
from app.gui.blocks.workspace_controller import BlockWorkspaceController
from app.gui.blocks.workspace_widget import BlockWorkspaceWidget


class BlockProjectDialog(QDialog):
    """Compatibility entry; shares one ProjectSession, no second state."""

    def __init__(
        self,
        registry: BlockRegistry | None = None,
        *,
        layout=None,
        table_model: TableEditorModel | None = None,
        merge_result: MergeResult | None = None,
        theme: AppTheme | None = None,
        document_theme: DocumentTheme | None = None,
        project_dir: Path | None = None,
        session: ProjectSession | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Block 项目（MVP）")
        self.resize(900, 640)

        if session is not None:
            self.session = session
        else:
            self.session = ProjectSession(
                registry=registry,
                layout=layout,
                document_theme=document_theme,
                app_theme=theme if isinstance(theme, AppTheme) else None,
                project_dir=project_dir,
            )
            if table_model is not None:
                self.session.table_model = table_model
        self.project_dir = self.session.project_dir
        self.registry = self.session.registry
        self.document_theme = self.session.document_theme

        self.workspace = BlockWorkspaceWidget(self.session, merge_result=merge_result)
        self.layout_panel = self.workspace.layout_panel
        self.table_editor = self.workspace.table_editor
        self.theme_settings = self.workspace.theme_settings
        self.controller = BlockWorkspaceController(self.session, self.workspace)

        layout_box = QVBoxLayout(self)
        layout_box.addWidget(self.workspace)
        self.workspace.preview_requested.connect(self._run_preview)

    def _run_preview(self) -> None:
        if self.project_dir is None:
            return
        self._build_pdf_sync()

    def _build_pdf_sync(self) -> object:
        """Legacy synchronous preview entry; routed through the session."""
        return self.session.compile_final()

    def _sync_table_to_registry(self) -> None:
        self.session.sync_table_to_registry()
