"""Read-only workspace presentation, composed from existing window-owned state.

This is not a second project/session store. Refreshes are coalesced and never
read project contents, create managers, write files or authorize compilation.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt, Slot
from PySide6.QtGui import QAction, QTextCursor
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMenu, QPlainTextEdit, QSizePolicy, QToolBar, QToolButton,
                               QVBoxLayout, QWidget)

from app.core.compiler import BuildPurpose
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness, FRESHNESS_LABELS
from app.core.preview_state import FRESHNESS_LABELS as PREVIEW_LABELS
from app.core.submission_check import CheckStatus, STATUS_LABELS


class _SummaryLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.full_text = ""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def describe(self, text):
        self.full_text = text
        self.setToolTip(text)
        self.setAccessibleName(text)
        shortened = self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, max(1, self.width()))
        if shortened != self.text():
            self.setText(shortened)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.describe(self.full_text)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() is QEvent.Type.FontChange and hasattr(self, "full_text"):
            self.describe(self.full_text)


class _DetailsText(QPlainTextEdit):
    """Full, selectable status text in a bounded, font-aware reading area."""

    def __init__(self):
        super().__init__()
        self.full_text = ""
        self.setObjectName("workspaceDetails")
        self.setAccessibleName("项目状态（只读）")
        self.setReadOnly(True)
        self.setTabChangesFocus(True)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._resize_to_font()

    def describe(self, text):
        if text == self.full_text:
            return
        previous = self.textCursor()
        anchor, position = previous.anchor(), previous.position()
        scroll = self.verticalScrollBar().value()
        self.full_text = text
        self.setPlainText(text)
        cursor = self.textCursor()
        end = self.document().characterCount() - 1
        cursor.setPosition(min(anchor, end))
        cursor.setPosition(min(position, end), QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        self.verticalScrollBar().setValue(scroll)

    def _resize_to_font(self):
        self.setFixedHeight(self.fontMetrics().lineSpacing() * 3 +
                            round(self.document().documentMargin() * 2) + 2 * self.frameWidth() + 4)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._resize_to_font()


class WorkspaceController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self._closed = False
        self.bar = QWidget()
        self.bar.setObjectName("workspaceHeader")
        self.bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.title = _SummaryLabel()
        self.title.setObjectName("workspaceSummary")
        self.details = _DetailsText()
        self.details.hide()
        self.next_button = QToolButton()
        self.next_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.navigation = QToolButton()
        self.navigation.setText("项目导航")
        self.navigation.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu = QMenu(self.navigation)
        self.menu.aboutToShow.connect(self._build_navigation)
        self.navigation.setMenu(self.menu)
        row = QHBoxLayout()
        row.addWidget(self.title, 1)
        row.addWidget(self.navigation)
        row.addWidget(self.next_button)
        layout = QVBoxLayout(self.bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addLayout(row)
        layout.addWidget(self.details)
        self.save_action = QAction("保存项目文档", self)
        self.save_action.triggered.connect(self._save_project)
        # Ordinary writing shares the main toolbar row; Block keeps a separate
        # row when its context requires more controls.
        self.toolbar = QToolBar("项目工作区", window)
        self.toolbar.setObjectName("workspaceToolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.addWidget(self.bar)
        window.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbar)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self.refresh)
        window.editor_tabs.currentChanged.connect(self.schedule)
        window.signals.started.connect(self.schedule)
        window.signals.finished.connect(self.schedule)
        window.signals.external_changed.connect(self.schedule)
        window.engine_selector.currentIndexChanged.connect(self.schedule)
        self.refresh()

    def _block(self):
        window = self.window
        return window.block_session if window.block_mode_action.isChecked() else None

    def _source_context(self):
        window = self.window
        tab = window.current_tab()
        # Opening resolves dependencies but does not create a CompileManager.
        root = window.dependencies.root_for_tab(tab)
        scope = window.selected_project_scope or (root.parent if root else None)
        dependencies = window.dependencies.paths_for(root) if root else frozenset()
        tabs = tuple(item for item in window.tabs.values() if item is tab or
                     root is not None and ((window.dependencies.root_for_tab(item) == root)
                                           or item.path in dependencies))
        return tab, root, scope, tabs

    @Slot()
    def schedule(self):
        if self._closed:
            return
        if not self._timer.isActive():
            self._timer.start()

    @Slot()
    def refresh(self):
        if self._closed:
            return
        window = self.window
        session = self._block()
        tab, source_root, source_scope, tabs = self._source_context()
        root = (session.project_dir / "main.tex" if session.project_dir else None) if session else source_root
        scope = session.project_dir if session else source_scope
        report = window.submission_panel.report
        items = report.items if report and all(item.scope == str(root) for item in report.items) else ()
        rules = {item.rule_id: item for item in items}
        check_text = "提交检查：待刷新"
        if rules:
            failures = sum(item.status is CheckStatus.FAIL for item in items)
            unknown = sum(item.status is CheckStatus.UNKNOWN for item in items)
            check_text = f"提交检查：{failures} 项未通过 / {unknown} 项未知"
        if window.readiness.is_busy:
            check_text = "提交检查中"
        if session:
            engine = session.compile_manager.engine if session.compile_manager else LaTeXEngine.XELATEX
            save_text = (f"{len(session.editor_drafts)} 份编辑草稿待应用" if session.editor_drafts else
                         "保存受阻，草稿保留" if session.save_error else
                         "模型待保存" if session.has_unsaved_changes else
                         STATUS_LABELS[rules["saved"].status] if "saved" in rules else "磁盘一致性待检查")
            result = session.last_result
            current = (result and result.job_key and result.job_key.root_file == root
                       and result.job_key.source_revision == session._revision
                       and result.ok and window.pdf_panel.current_pdf == result.pdf_file)
            pdf_text = (f"{result.purpose.value.upper()}（输入待核对）" if current else "无当前模型产物")
            if "pdf_current" in rules and rules["pdf_current"].status is CheckStatus.PASS:
                pdf_text = "FINAL（已核对输入）"
            if session.editor_drafts:
                pdf_text += " · 不含待应用编辑草稿"
            if session.final_is_running:
                pdf_text = "FINAL 编译中，旧显示不作当前提交"
            if session.recovery_pending:
                save_text += " · 恢复草稿，首次保存前不自动写入"
            if session.has_unsaved_changes:
                action, next_text = window.block_save_action, "保存 Block 草稿"
            elif session.save_error:
                action, next_text = window.submission_check_action, "核对保存问题"
            elif session.compile_manager and session.compile_manager.is_busy:
                action, next_text = window.block_stop_action, "停止 Block 编译"
            elif not current:
                action, next_text = window.block_compile_action, "正式编译 Block 项目"
            else:
                action, next_text = window.submission_check_action, "核对 Block 项目"
        else:
            engine = tab.manager.engine if tab and tab.manager else window.current_engine
            conflict = any(item.external_conflict for item in tabs)
            dirty = any(item.modified or item.dirty or item.path is None for item in tabs)
            save_text = "有外部冲突" if conflict else "有未保存内容" if dirty else "已保存" if tab else "尚无文档"
            if any(item.recovery_pending for item in tabs):
                save_text += " · 恢复草稿，首次保存前不自动写入"
            record = window.pdf_state.record_for(root) if root else None
            displayed = window.displayed_pdfs.get(root) if root else None
            if displayed and window.pdf_panel.current_pdf == displayed.path:
                if displayed.purpose is BuildPurpose.PREVIEW:
                    preview = window.preview_state.record_for(root)
                    pdf_text = "快速预览 · " + PREVIEW_LABELS[preview.freshness]
                else:
                    pdf_text = "正式 PDF · " + FRESHNESS_LABELS[record.freshness]
            else:
                pdf_text = FRESHNESS_LABELS[record.freshness] if record else "未编译"
            if tab is None:
                action, next_text = window.new_project_action, "创建项目"
            elif tab.path is None:
                action, next_text = window.save_as_action, "保存文档"
            elif conflict:
                action, next_text = window.submission_check_action, "查看保存冲突"
            elif dirty:
                action, next_text = self.save_action, "保存项目文档"
            elif not window.toolchain.supports_engine(engine):
                action, next_text = window.environment_doctor_action, "检查 LaTeX 环境"
            elif record and record.freshness is PdfFreshness.COMPILING:
                action, next_text = window.stop_compile_action, "停止编译"
            elif record and record.freshness is PdfFreshness.CURRENT:
                checked_pdf = rules.get("pdf_current")
                failures = any(item.status is CheckStatus.FAIL for item in rules.values())
                if checked_pdf and checked_pdf.status is CheckStatus.PASS and not failures:
                    action, next_text = window.export_pdf_action, "导出正式 PDF"
                else:
                    action, next_text = window.submission_check_action, "核对提交输入"
            else:
                action, next_text = window.compile_action, "首次正式编译" if not record or record.latest_build_id == 0 else "重新正式编译"
        mode = "Block（元数据驱动）" if session else "源码（LaTeX 为准）"
        name = scope.name if scope else "未选择项目"
        entry = str(root.relative_to(scope)) if root and scope and root.is_relative_to(scope) else "待确认"
        self.title.describe(f"{name} · {'Block' if session else '文档'}：{save_text}")
        self.details.describe(f"入口：{entry}\n保存：{save_text}\n引擎：{engine.display_name}\nPDF：{pdf_text}\n{check_text}")
        self.title.setToolTip(f"{name} · {mode}\n{self.details.full_text}\n{check_text}")
        self._check_text = check_text
        self.next_button.setDefaultAction(action)
        self.next_button.setText(next_text)
        self.next_button.setToolTip("显式执行下一步；不会因状态变化而自动运行。")
        self.next_button.setVisible(action not in (window.compile_action, window.stop_compile_action,
            window.block_save_action, window.block_compile_action, window.block_stop_action))
        window.status_engine_label.setText(engine.display_name)

    @Slot()
    def _save_project(self):
        tab, root, _, _ = self._source_context()
        if self._block() is not None:
            return
        if root is None:
            self.window.save_current()
        elif not self.window.documents.request_root_save(root):
            self.window.statusBar().showMessage("项目尚未全部保存；请先处理冲突或另存为。", 5000)
        self.window.readiness.invalidate()
        self.schedule()

    @Slot()
    def _build_navigation(self):
        self.menu.clear()
        window = self.window
        details = self.menu.addAction("展开项目状态")
        details.setCheckable(True)
        details.setChecked(not self.details.isHidden())
        details.toggled.connect(self.details.setVisible)
        self.menu.addSection(getattr(self, "_check_text", "提交检查：待刷新"))
        if self._block():
            for action in (window.block_save_action, window.block_compile_action, window.block_stop_action):
                self.menu.addAction(action)
            self.menu.addSeparator()
            for key in ("navigation", "inspector", "diagnostics"):
                self.menu.addAction(window.block_panels.docks[key].toggleViewAction())
            self.menu.addSeparator()
            for label, index in (("内容", 0), ("布局", 1), ("素材与来源", 2)):
                self.menu.addAction(label).triggered.connect(lambda _checked=False, index=index: self._block_navigation(index))
        else:
            for label, index in (("项目文件", 0), ("章节", 1), ("素材", 3), ("引用", 7),
                                 ("历史", 4), ("插入图表与公式", 5), ("模板", 6)):
                self.menu.addAction(label).triggered.connect(lambda _checked=False, index=index: self._source_navigation(index))
        self.menu.addSeparator()
        for action in (window.submission_check_action, window.project_profile_action,
                       window.environment_doctor_action, window.user_guide_action):
            self.menu.addAction(action)

    def _source_navigation(self, index):
        if self._block() is not None:
            return
        self.window.toolbox_action.setChecked(True)
        self.window.sidebar_tabs.setCurrentIndex(index)
        self.window.project_panels.refresh_visible()

    def _block_navigation(self, index):
        if self._block() is not None:
            self.window.block_panels.request("navigation")
            self.window.block_nav.tabs.setCurrentIndex(index)

    def shutdown(self):
        self._closed = True
        self._timer.stop()
