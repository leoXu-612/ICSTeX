"""An opt-in exercise in its own window; ordinary writing has no tutorial timer."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QSettings, QStandardPaths, QTimer, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import QApplication, QDockWidget, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget
from shiboken6 import isValid

from app.core.artifact_export import ExportedPdf
from app.core.compiler import BuildPurpose
from app.core.latex_tools import LaTeXEngine
from app.core.pdf_state import PdfFreshness
from app.core.preview_state import PreviewFreshness
from app.core.project_dependencies import safe_project_input
from app.core.settings import AppSettings
from app.core.text_positions import utf16_length
from app.core.tutorial import INITIAL_TITLE, TutorialStep, create_example, existing_example, title_span, tutorial_step
from app.gui.responsive.helpers import ButtonFlowLayout
from app.gui.theme import PRIMARY_BUTTON_STATE_STYLE

if TYPE_CHECKING:
    from app.gui.main_window import MainWindow

EXAMPLE_SETTING = "tutorial/last_example"


def example_directory() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "tutorials"


def remembered_example(window: MainWindow) -> Path | None:
    return existing_example(example_directory(), window.app_settings.settings.value(EXAMPLE_SETTING))


def open_example(owner: MainWindow, root: Path | None = None) -> MainWindow | None:
    """Explicit user action. Never clear the owner's tabs or overwrite an old example."""
    base = example_directory().resolve()
    try:
        if root is None:
            root = create_example(base)
        elif existing_example(base, str(root)) is None:
            raise ValueError("上次的练习文件找不到了，或路径已变化。请在新手导引里另建一个副本。")
        for window in getattr(QApplication.instance(), "_icstex_windows", []):
            if not isValid(window):
                continue
            controller = getattr(window, "tutorial", None)
            if controller is not None and controller.root == root:
                controller.resume()
                window.show()
                window.raise_()
                window.activateWindow()
                return window
        settings_path = safe_project_input(base, base / (root.parent.name + ".ini"), allow_internal=True)
        if settings_path is None:
            raise ValueError("练习设置的路径不可用。请另建一个副本。")
        settings = AppSettings(QSettings(str(settings_path), QSettings.Format.IniFormat))
        first_open = not settings.settings.contains("editor/default_engine")
        preferences = (replace(owner.preferences, default_engine=LaTeXEngine.AUTO)
                       if first_open else settings.load_preferences())
        # UI scale is application-wide. An old exercise profile must not restyle
        # the owner's windows when this independent window is reopened.
        scale = getattr(QApplication.instance(), "ui_scale_manager").scale
        if first_open or preferences.ui_scale != scale:
            settings.save_preferences(replace(preferences, ui_scale=scale))
        settings.settings.setValue(EXAMPLE_SETTING, str(root))
        window = owner.spawn_window(settings_store=settings)
        window.project_files.set_project_root(root.parent, remember=False)
        window.open_file(root)
        if window._tab_for_path(root) is None:
            window.close()
            raise ValueError("练习文件没有打开。可以另建一个副本，已经写下的内容不会被覆盖。")
        window.tutorial = TutorialController(window, root)
        window.tutorial.resume()
        owner.app_settings.settings.setValue(EXAMPLE_SETTING, str(root))
        owner.app_settings.settings.sync()
        return window
    except (OSError, ValueError) as exc:
        QMessageBox.warning(owner, "练习没有打开", str(exc))
        return None


class TutorialController(QObject):
    def __init__(self, window: MainWindow, root: Path) -> None:
        super().__init__(window)
        self.window, self.root = window, root
        self.active = False
        self.manual_requested = False
        self.seen = None
        self.exported: tuple[ExportedPdf, int, int] | None = None
        self.step = TutorialStep.EDIT
        self._secondary_role = "help"
        self._editor = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self.refresh)
        self.dock = QDockWidget("写作练习 · 原稿留在原窗口", window)
        self.dock.setObjectName("writingTutorialDock")
        self.dock.setAllowedAreas(Qt.DockWidgetArea.TopDockWidgetArea)
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable)
        panel = QWidget()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        self.title = QLabel()
        self.description = QLabel()
        for label in (self.title, self.description):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            layout.addWidget(label)
        self.action = QPushButton()
        self.action.setObjectName("primaryButton")
        self.action.setStyleSheet(PRIMARY_BUTTON_STATE_STYLE)
        self.secondary = QPushButton()
        self.hide_button = QPushButton("收起导引")
        self.hide_button.setToolTip("练习内容会保留；从“帮助 → 新手导引”点“继续上次练习”可以回来。")
        row = ButtonFlowLayout()
        for button in (self.action, self.secondary, self.hide_button):
            row.addWidget(button)
        layout.addLayout(row)
        self.dock.setWidget(panel)
        window.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, self.dock)
        self.action.clicked.connect(self.act)
        self.secondary.clicked.connect(self.secondary_action)
        self.hide_button.clicked.connect(self.dock.hide)
        self.dock.visibilityChanged.connect(self._visibility)
        window.editor_tabs.currentChanged.connect(self.schedule)
        window.signals.started.connect(self.schedule)
        window.signals.finished.connect(self.schedule)
        window.signals.external_changed.connect(self.schedule)
        window.pdf_panel.availabilityChanged.connect(self.schedule)
        window.pdf_panel.viewChanged.connect(self.schedule)
        window.block_mode_action.toggled.connect(self.schedule)
        window.compile_action.triggered.connect(self._manual_compile)
        window.pdf_export.exportSucceeded.connect(self._export_succeeded)

    @Slot(bool)
    def _visibility(self, visible: bool) -> None:
        self.active = visible
        if visible:
            self.schedule()
        else:
            self._timer.stop()

    def resume(self) -> None:
        self.active = True
        self.dock.show()
        self.refresh()

    @Slot()
    def schedule(self) -> None:
        if self.active:
            self._timer.start()

    @Slot()
    def _manual_compile(self) -> None:
        tab = self.window.current_tab()
        if tab is not None and tab.path == self.root and not self.window.block_mode_action.isChecked():
            self.manual_requested = True
            self.schedule()

    @Slot(object, object, int, int)
    def _export_succeeded(self, root: Path, exported: ExportedPdf, revision: int, build_id: int) -> None:
        if root == self.root:
            self.exported = (exported, revision, build_id)
            self.schedule()

    def _current_export(self) -> bool:
        """Match a published receipt; refresh also requires the same viewed, current PDF.

        This is tutorial progress, not a new export authorization or file-validity cache.
        """
        if self.exported is None or self.seen is None or self.seen.purpose is not BuildPurpose.FINAL:
            return False
        _, revision, build_id = self.exported
        record = self.window.pdf_state.record_for(self.root)
        return (record.freshness is PdfFreshness.CURRENT
                and revision == record.source_revision == record.last_successful_revision
                and build_id == record.latest_build_id)

    def _engine_ready(self, tab) -> bool:
        return self.window.toolchain.supports_engine(tab.manager.engine if tab.manager else LaTeXEngine.XELATEX)

    def _current_pdf(self) -> bool:
        window = self.window
        tab = window._tab_for_path(self.root)
        if (tab is None or tab.dirty or tab.modified or tab.external_conflict
                or (tab.manager is not None and tab.manager.is_busy)):
            return False
        displayed = window.displayed_pdfs.get(self.root)
        panel = window.pdf_panel
        if (displayed is None or not panel._has_pages or panel.current_logical_key != self.root
                or panel.current_pdf != displayed.path):
            return False
        if displayed.purpose is BuildPurpose.FINAL:
            record = window.pdf_state.record_for(self.root)
            current = record.freshness is PdfFreshness.CURRENT
        else:
            record = window.preview_state.record_for(self.root)
            current = record.freshness is PreviewFreshness.CURRENT
        return (current and record.has_valid_pdf
                and displayed.revision == record.source_revision == record.last_successful_revision
                and displayed.build_id == record.latest_build_id and displayed.path == record.last_successful_pdf)

    @Slot()
    def refresh(self) -> None:
        if not self.active:
            return
        window, tab = self.window, self.window.current_tab()
        if self._editor is not None and isValid(self._editor):
            if tab is None or self._editor is not tab.editor:
                self._editor.textChanged.disconnect(self.schedule)
                self._editor = None
        if tab is not None and self._editor is not tab.editor:
            self._editor = tab.editor
            self._editor.textChanged.connect(self.schedule)
        self.action.setEnabled(True)
        self.secondary.setText("图文教程")
        self._secondary_role = "help"
        if tab is None or tab.path != self.root or window.block_mode_action.isChecked():
            self.title.setText("先回到练习文件")
            self.description.setText("练习在 main.tex 中。点击下面的按钮回去，不会关闭其他文档。")
            self.action.setText("打开练习文件")
            return
        self.step = tutorial_step(tab.editor.toPlainText(), manual_requested=self.manual_requested,
            current_pdf=self._current_pdf(), acknowledged=self.seen == window.displayed_pdfs.get(self.root),
            exported=self._current_export())
        busy = bool(tab.manager and tab.manager.is_busy)
        if self.step is TutorialStep.EDIT:
            self.title.setText("1/4 · 改一下标题")
            self.description.setText(f"点击“选中标题”，把“{INITIAL_TITLE}”换成自己的标题。只改大括号里面的字。")
            self.action.setText("选中标题")
        elif self.step is TutorialStep.COMPILE:
            self.title.setText("2/4 · 生成 PDF")
            self.description.setText("点击“正式编译”，把文字排成 PDF。重开练习后也请编译一次，确认右边是最新内容。")
            self.action.setText("正式编译")
            if busy:
                self.description.setText("正在生成 PDF，请稍等。你可以从顶部工具栏停止编译。")
                self.action.setText("正在编译…")
            elif not self._engine_ready(tab):
                self.description.setText("本机还没找到 LaTeX 工具。先点“检查环境”查看安装办法，练习内容会保留。")
                self.action.setText("检查环境")
            elif (window.pdf_state.record_for(self.root).freshness in (PdfFreshness.FAILED_STALE, PdfFreshness.FAILED_NO_PDF)
                  or window.preview_state.record_for(self.root).freshness in (PreviewFreshness.FAILED_STALE, PreviewFreshness.FAILED_NO_PDF)):
                self.description.setText("这次没编译成功。点“查看错误”，先处理第一条提示，再点“正式编译”。")
                self.secondary.setText("查看错误")
                self._secondary_role = "errors"
            self.action.setEnabled(not busy)
        elif self.step is TutorialStep.VIEW:
            self.title.setText("3/4 · 在 PDF 中找到新标题")
            self.description.setText("右边应该已经出现你刚写的标题。窗口较窄时，先点“显示 PDF”。看到后再确认。")
            self.action.setText("我看到了新标题")
            self.action.setEnabled(window.pdf_panel.isVisibleTo(window))
            self.secondary.setText("显示 PDF")
            self._secondary_role = "pdf"
        elif self.step is TutorialStep.EXPORT:
            self.title.setText("4/4 · 导出一份 PDF")
            self.description.setText("点“导出 PDF”，选位置并点“更新并导出”。PDF 下方会显示进度和结果；取消或失败都可以重新试。")
            self.action.setText("导出 PDF…")
        else:
            self.title.setText("练习完成 · PDF 已导出")
            self.description.setText(f"已导出到：{self.exported[0].target}\n可以打开文件夹查看；要保留固定版本，点 PDF 下方的“停止更新”。")
            self.action.setText("打开导出文件夹")

    @Slot()
    def act(self) -> None:
        self.refresh()
        window, tab = self.window, self.window.current_tab()
        if tab is None or tab.path != self.root or window.block_mode_action.isChecked():
            if existing_example(example_directory(), str(self.root)) is not None:
                if window.block_mode_action.isChecked():
                    window.block_mode_action.trigger()
                window.open_file(self.root)
            else:
                QMessageBox.warning(window, "练习文件不可用", "请从新手导引另建一个副本；不会覆盖原来的内容。")
            self.schedule()
            return
        if self.step is TutorialStep.EDIT:
            text = tab.editor.toPlainText()
            span = title_span(text)
            if span is None:
                self.description.setText("这个练习需要一行普通文字标题，例如 \\title{我的文章}。可以先撤销刚才的改动，或另建一个练习副本。")
                return
            window.source_preview_area.select_pdf(False)
            cursor = tab.editor.textCursor()
            cursor.setPosition(utf16_length(text[:span[0]]))
            cursor.setPosition(utf16_length(text[:span[1]]), QTextCursor.MoveMode.KeepAnchor)
            tab.editor.setTextCursor(cursor)
            tab.editor.setFocus()
        elif self.step is TutorialStep.COMPILE:
            if not tab.manager or not tab.manager.is_busy:
                if self._engine_ready(tab):
                    window.compile_action.trigger()
                else:
                    window.show_environment_doctor()
                    self.schedule()
        elif self.step is TutorialStep.VIEW:
            if self._current_pdf() and window.pdf_panel.isVisibleTo(window):
                self.seen = window.displayed_pdfs.get(self.root)
                self.refresh()
        elif self.step is TutorialStep.EXPORT:
            window.export_pdf()
        else:
            target = self.exported[0].target
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.parent))):
                window.statusBar().showMessage("无法打开导出文件夹；可以按上面的路径查找 PDF。", 6000)

    @Slot()
    def secondary_action(self) -> None:
        if self._secondary_role == "pdf":
            self.window.source_preview_area.select_pdf(True)
            self.refresh()
        elif self._secondary_role == "errors":
            from app.gui.main_window_layout import show_console
            show_console(self.window, self.window.diagnostic_panel)
        else:
            self.window.show_user_guide()
