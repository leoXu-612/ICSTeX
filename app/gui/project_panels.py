from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.history import HistorySnapshot
from app.core.image_assets import ImageAsset
from app.core.latex_insertions import all_templates
from app.core.latex_tools import LaTeXEngine
from app.core.magic_comments import parse_magic_comments
from app.core.project_profile import ProjectProfile
from app.core.latex_outline import OutlineItem
from app.core.project_search import ProjectSearchResult
from app.core.project_tools import (BibEntrySpec, LabelInfo, ProjectInitSpec,
                                    initialize_project, sanitize_project_name)


_IMAGE_THUMBNAIL_SIZE = QSize(44, 44)
_IMAGE_THUMBNAIL_CACHE_LIMIT = 128


class _ImageThumbnailCache:
    """Decode small image previews once without retaining source-size pixels."""

    def __init__(self, *, max_entries: int, target_size: QSize) -> None:
        self._max_entries = max(1, max_entries)
        self._target_size = QSize(target_size)
        self._entries: OrderedDict[tuple[str, int, int], QIcon] = OrderedDict()

    def icon_for(self, path: Path) -> QIcon:
        try:
            resolved = path.expanduser().resolve()
            stat = resolved.stat()
        except OSError:
            return QIcon()

        path_key = str(resolved)
        key = (path_key, stat.st_mtime_ns, stat.st_size)
        cached = self._entries.get(key)
        if cached is not None:
            self._entries.move_to_end(key)
            return cached

        # Drop an older version of the same file immediately instead of
        # waiting for normal LRU eviction after an on-disk edit.
        for existing_key in tuple(self._entries):
            if existing_key[0] == path_key:
                self._entries.pop(existing_key)

        icon = self._decode_icon(resolved)
        self._entries[key] = icon
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
        return icon

    def _decode_icon(self, path: Path) -> QIcon:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        source_size = reader.size()
        if source_size.isValid():
            scaled_size = source_size.scaled(self._target_size, Qt.AspectRatioMode.KeepAspectRatio)
            scaled_size.setWidth(max(1, scaled_size.width()))
            scaled_size.setHeight(max(1, scaled_size.height()))
        else:
            scaled_size = self._target_size
        reader.setScaledSize(scaled_size)
        image = reader.read()
        if image.isNull():
            return QIcon()
        if image.width() > self._target_size.width() or image.height() > self._target_size.height():
            image = image.scaled(
                self._target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return QIcon(QPixmap.fromImage(image))


class ProjectWizardDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建 LaTeX 项目")
        self.resize(600, 600)
        self.created_project = None
        self._templates = {template.key: template for template in all_templates()}
        self.parent_edit = QLineEdit(str(Path.home()))
        self.name_edit = QLineEdit("LaTeX 项目")
        self.template_combo = QComboBox()
        for template in self._templates.values():
            self.template_combo.addItem(template.title, template.key)
        self.engine_combo = QComboBox()
        for engine in LaTeXEngine:
            self.engine_combo.addItem(engine.display_name, engine.value)
        self.engine_combo.setCurrentIndex(self.engine_combo.findData(LaTeXEngine.AUTO.value))
        self.profile_enabled = QCheckBox("保存可编辑的项目配置（不设课程字数限制）")
        self.profile_enabled.setChecked(True)
        self.open_new_window = QCheckBox("在新窗口打开（保留当前工作区）")
        self.open_new_window.setChecked(bool(parent and hasattr(parent, "current_tab") and
                                            (parent.current_tab() or getattr(parent, "block_session", None))))
        self.destination = QLabel()
        self.destination.setTextFormat(Qt.TextFormat.PlainText)
        self.destination.setWordWrap(True)
        self.template_hint = QLabel()
        self.template_hint.setWordWrap(True)
        self.template_hint.setTextFormat(Qt.TextFormat.PlainText)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName("新项目模板源码预览")
        self.preview.setMaximumHeight(160)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setTextFormat(Qt.TextFormat.PlainText)
        self._build()
        self.parent_edit.textChanged.connect(self._update_destination)
        self.name_edit.textChanged.connect(self._update_destination)
        self.template_combo.currentIndexChanged.connect(self._update_template)
        self.engine_combo.currentIndexChanged.connect(self._update_template)
        self._update_destination()
        self._update_template()

    def values(self) -> ProjectInitSpec:
        key = str(self.template_combo.currentData())
        suggested = parse_magic_comments(self._templates[key].text).program
        engine = self.selected_engine()
        profile = ProjectProfile(template=key, engine=(suggested.value if suggested else "")
                                 if engine is LaTeXEngine.AUTO else engine.value)
        return ProjectInitSpec(
            parent_dir=Path(self.parent_edit.text().strip() or str(Path.home())),
            project_name=self.name_edit.text().strip(),
            template_key=key,
            profile=profile if self.profile_enabled.isChecked() else None,
        )

    def selected_engine(self):
        return LaTeXEngine(self.engine_combo.currentData())

    def _update_destination(self):
        name = sanitize_project_name(self.name_edit.text())
        parent = Path(self.parent_edit.text().strip() or str(Path.home())).expanduser()
        changed = name != self.name_edit.text().strip()
        self.destination.setText(f"创建位置：{parent / name}\n"
                                 + (f"名称将调整为：{name}。" if changed else "")
                                 + "目标必须是新目录；已有文件夹不会覆盖。")

    def _update_template(self):
        template = self._templates[str(self.template_combo.currentData())]
        self.preview.setPlainText(template.text)
        suggested = parse_magic_comments(template.text).program
        engine = self.selected_engine()
        effective = suggested if engine is LaTeXEngine.AUTO and suggested else engine
        tools = getattr(self.parentWidget(), "toolchain", None)
        ready = tools.supports_engine(effective) if tools else False
        self.template_hint.setText(
            f"引擎选择：{engine.display_name}；模板声明：{suggested.display_name if suggested else '无'}。\n"
            + ("本机已检测到可用工具。" if ready else "工具尚未就绪也可创建和编辑；之后通过环境医生查看安装指引。")
            + "创建不会运行编译器。首次编译由你主动触发。")

    def accept(self):
        try:
            self.created_project = initialize_project(self.values())
        except (OSError, ValueError) as exc:
            self.error.setText(str(exc))
            return
        super().accept()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        intro = QLabel("选择模板 → 创建项目 → 编辑图表与引用 → 正式编译 → 提交检查与导出。")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        form = QFormLayout(body)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.addRow("父文件夹", self._folder_row())
        form.addRow("项目名称", self.name_edit)
        form.addRow("模板", self.template_combo)
        form.addRow("编译器", self.engine_combo)
        form.addRow(self.template_hint)
        form.addRow(self.profile_enabled)
        form.addRow(self.open_new_window)
        form.addRow(self.destination)
        form.addRow("模板预览", self.preview)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("创建项目")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _folder_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        button = QPushButton("浏览")
        button.clicked.connect(self._browse_parent)
        layout.addWidget(self.parent_edit)
        layout.addWidget(button)
        return row

    def _browse_parent(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择父文件夹", self.parent_edit.text())
        if folder:
            self.parent_edit.setText(folder)


class BibEntryDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("添加引用")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["article", "book", "misc", "online"])
        self.key_edit = QLineEdit()
        self.author_edit = QLineEdit()
        self.title_edit = QLineEdit()
        self.year_edit = QLineEdit()
        self.journal_edit = QLineEdit()
        self.publisher_edit = QLineEdit()
        self.url_edit = QLineEdit()
        self._build()

    def values(self) -> BibEntrySpec:
        return BibEntrySpec(
            entry_type=self.type_combo.currentText(),
            key=self.key_edit.text().strip(),
            author=self.author_edit.text().strip(),
            title=self.title_edit.text().strip(),
            year=self.year_edit.text().strip(),
            journal=self.journal_edit.text().strip(),
            publisher=self.publisher_edit.text().strip(),
            url=self.url_edit.text().strip(),
        )

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("类型", self.type_combo)
        form.addRow("Bib key", self.key_edit)
        form.addRow("作者", self.author_edit)
        form.addRow("标题", self.title_edit)
        form.addRow("年份", self.year_edit)
        form.addRow("期刊", self.journal_edit)
        form.addRow("出版社", self.publisher_edit)
        form.addRow("URL", self.url_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class BibImportDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("快速导入引用")
        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("粘贴 BibTeX、DOI、arXiv ID、URL 或文献标题")
        self.input_edit.setMinimumHeight(180)
        self.online_check = QCheckBox("联网获取真实元数据（仅 DOI/arXiv，需要联网）")
        self._build()

    def text(self) -> str:
        return self.input_edit.toPlainText().strip()

    def online(self) -> bool:
        return self.online_check.isChecked()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        hint = QLabel("默认离线：DOI/arXiv/URL 会先生成可编辑 BibTeX 骨架。勾选下方选项可联网抓取真实元数据，只会发送你输入的标识符。")
        hint.setObjectName("panelHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addWidget(self.input_edit)
        layout.addWidget(self.online_check)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class ReferencesPanel(QWidget):
    addReferenceRequested = Signal()
    importReferenceRequested = Signal()
    refreshRequested = Signal()
    citeRequested = Signal(str)
    checkRequested = Signal()
    cancelCheckRequested = Signal()
    locationRequested = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("referencesPanel")
        outer = QVBoxLayout(self)
        self.reference_tabs = QTabWidget()
        outer.addWidget(self.reference_tabs)
        library = QWidget()
        layout = QVBoxLayout(library)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        buttons = QHBoxLayout()
        self.add_button = QPushButton("添加")
        self.import_button = QPushButton("导入")
        self.refresh_button = QPushButton("刷新")
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.import_button)
        buttons.addWidget(self.refresh_button)
        layout.addLayout(buttons)

        self.table = QTableWidget(0, 1)
        self.table.setHorizontalHeaderLabels(["Bib key"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.status_label = QLabel("未加载引用")
        self.status_label.setObjectName("panelHint")
        layout.addWidget(self.status_label)

        self.insert_button = QPushButton("插入 cite")
        self.insert_button.setObjectName("primaryButton")
        layout.addWidget(self.insert_button)

        self.check_button = QPushButton("检查项目引用（只读）")
        self.check_button.clicked.connect(self.checkRequested.emit)
        layout.addWidget(self.check_button)
        self.reference_tabs.addTab(library, "快捷库")

        health = QWidget()
        health_layout = QVBoxLayout(health)
        health_buttons = QHBoxLayout()
        self.check_refresh_button = QPushButton("重新检查")
        self.check_refresh_button.clicked.connect(self.checkRequested.emit)
        self.check_cancel_button = QPushButton("取消")
        self.check_cancel_button.clicked.connect(self.cancelCheckRequested.emit)
        health_buttons.addWidget(self.check_refresh_button)
        health_buttons.addWidget(self.check_cancel_button)
        health_layout.addLayout(health_buttons)
        self.check_status = QLabel("尚未检查；不保存、不编译、不联网。")
        self.check_status.setWordWrap(True)
        health_layout.addWidget(self.check_status)
        self.health_table = QTableWidget(0, 3)
        self.health_table.setHorizontalHeaderLabels(["状态", "规则", "Bib key"])
        self.health_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.health_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.health_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.health_table.itemSelectionChanged.connect(self._show_citation_detail)
        health_layout.addWidget(self.health_table)
        self.check_detail = QPlainTextEdit()
        self.check_detail.setReadOnly(True)
        self.check_detail.setMinimumHeight(100)
        health_layout.addWidget(self.check_detail)
        self.check_locations = QListWidget()
        self.check_locations.itemActivated.connect(lambda _item: self._locate_citation())
        health_layout.addWidget(self.check_locations)
        self.check_locate_button = QPushButton("定位所选位置")
        self.check_locate_button.clicked.connect(self._locate_citation)
        health_layout.addWidget(self.check_locate_button)
        self.reference_tabs.addTab(health, "引用检查")
        self.citation_report = None
        self._citation_scope = None
        self.set_check_pending("尚未检查；不保存、不编译、不联网。")

        self.add_button.clicked.connect(self.addReferenceRequested.emit)
        self.import_button.clicked.connect(self.importReferenceRequested.emit)
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.insert_button.clicked.connect(self._emit_cite)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._emit_cite())

    def set_references(self, keys: list[str], undefined: set[str] | None = None) -> None:
        self.table.setRowCount(0)
        for key in keys:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(key))
        self.status_label.setText(f"约定位置快捷库：{len(keys)} 条；项目引用状态请主动检查。")
        self.status_label.setWordWrap(True)

    _CITATION_RULES = {
        "citation_missing": "未找到引用", "key_duplicate": "重复 key", "entry_unused": "未见静态使用（建议）",
        "entry_used": "已关联使用", "entry_usage_unknown": "使用范围未知", "bib_unparsed": "BibTeX 解析未完成",
        "citation_unparsed": "引用语法未解析", "dependency_unknown": "依赖范围未知",
        "input_unreadable": "输入不可读", "inputs_changed": "输入已变化", "root_unknown": "入口未知",
        "relation_missing": "未找到条目关联", "relation_unparsed": "条目关联未解析", "library_fallback": "约定位置回退库",
    }
    _CITATION_STATES = {"fail": "需处理", "unknown": "未知", "suggestion": "建议", "info": "信息"}
    _CITATION_HELP = {
        "citation_missing": "已读取的文献库未找到该 key；请定位使用处并核对拼写及文献库声明。",
        "key_duplicate": "多个条目使用同一个 key；请逐一核对定义，不会自动合并或删除。",
        "entry_unused": "在支持的静态语法中未见使用；这只是整理建议，请保留作者仍需要的文献。",
        "entry_used": "发现直接引用、nocite 或条目间关联；可定位定义及直接使用处。",
        "entry_usage_unknown": "检查范围不完整，不能据此认定该条目未使用。",
        "bib_unparsed": "部分 BibTeX 字段或结构未能解析；请查看技术原因并定位核对原文。",
        "citation_unparsed": "该处包含未支持或动态语法；不展开任意宏，也不据此判定编译失败。",
        "dependency_unknown": "无法确定完整的静态依赖范围；请核对入口、路径、动态声明及读取限制。",
        "input_unreadable": "相关输入缺失、受路径限制或无法安全读取；请选择仍可读取的关联源码位置。",
        "relation_missing": "未在已读取的文献库找到关联条目；请核对 crossref 等关联字段。",
        "relation_unparsed": "条目关联或别名未能静态解析，使用范围保持未知。",
        "library_fallback": "未找到明确的文献库声明，仅显示约定位置的快捷库，不能视为完整项目文献库。",
    }

    def set_check_pending(self, message, *, busy=False):
        self.citation_report = None
        self.health_table.setRowCount(0)
        self.check_detail.setPlainText(message)
        self.check_status.setText(message)
        self.check_locations.clear()
        self.check_locate_button.setEnabled(False)
        self.check_cancel_button.setEnabled(busy)

    def set_citation_report(self, report, scope, checked_at):
        self._citation_scope = scope
        self.citation_report = report
        self.health_table.blockSignals(True)
        self.health_table.setRowCount(len(report.items))
        for row, item in enumerate(report.items):
            for column, value in enumerate((self._CITATION_STATES.get(item.status, item.status),
                                            self._CITATION_RULES.get(item.rule, item.rule), item.key)):
                self.health_table.setItem(row, column, QTableWidgetItem(value))
        self.health_table.blockSignals(False)
        scope_label = "已检查支持的静态语法" if report.complete else "存在未解析或缺失输入"
        self.check_status.setText(f"检查记录：{checked_at}\n{scope_label}；不是编译结果或学术合规证明。")
        self.check_cancel_button.setEnabled(False)
        self.check_detail.setPlainText(f"输入身份：{report.input_id}\n选择规则查看位置。")
        self.check_locations.clear()
        self.check_locate_button.setEnabled(False)
        if report.items:
            self.health_table.selectRow(0)

    def _show_citation_detail(self):
        self.check_locations.clear()
        report = self.citation_report
        row = self.health_table.currentRow()
        if report is None or not 0 <= row < len(report.items):
            return
        item = report.items[row]
        title = self._CITATION_RULES.get(item.rule, item.rule)
        self.check_detail.setPlainText(
            f"{title} · {item.key}\n{self._CITATION_HELP.get(item.rule, title)}\n"
            f"技术记录：{item.message}\n输入身份：{report.input_id}\n"
            "只读检查；不展开任意宏，不评价文献真实性。未使用仅是静态建议，不自动删除。\n"
            "单文件 4 MiB、累计输入 32 MiB、2000 个输入；引用/条目、字段和关联各有 10000 项上限。\n"
            "缓冲区按本次内容检查，磁盘输入在结束前复核；这不是冻结备份。")
        modes = {path: kind for path, kind, _digest in report.inputs}
        for location in item.locations:
            label = location.path.relative_to(self._citation_scope).as_posix()
            mode = "缓冲区" if modes.get(location.path) == "buffer" else "磁盘/依赖位置"
            self.check_locations.addItem(QListWidgetItem(f"{label}:{location.line} · {mode}"))
        self.check_locate_button.setEnabled(bool(item.locations))
        if item.locations:
            self.check_locations.setCurrentRow(0)

    def _locate_citation(self):
        row = self.health_table.currentRow()
        location = self.check_locations.currentRow()
        if self.citation_report is not None and row >= 0 and location >= 0:
            self.locationRequested.emit(row, location)

    def _emit_cite(self) -> None:
        selected = self.table.selectedItems()
        if selected:
            self.citeRequested.emit(selected[0].text())


class OutlinePanel(QWidget):
    refreshRequested = Signal()
    jumpRequested = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("outlinePanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.refresh_button = QPushButton("刷新")
        layout.addWidget(self.refresh_button)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["标题", "类型", "行号"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        layout.addWidget(self.table)

        self.status_label = QLabel("未加载大纲")
        self.status_label.setObjectName("panelHint")
        layout.addWidget(self.status_label)

        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.table.cellDoubleClicked.connect(lambda row, _column: self._emit_jump(row))

    def set_outline(self, items: list[OutlineItem]) -> None:
        self.table.setRowCount(0)
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            title = QTableWidgetItem(f"{'  ' * max(0, item.level - 2)}{item.title}")
            title.setData(Qt.ItemDataRole.UserRole, item.line)
            self.table.setItem(row, 0, title)
            self.table.setItem(row, 1, QTableWidgetItem(item.command))
            self.table.setItem(row, 2, QTableWidgetItem(str(item.line)))
        self.status_label.setText(f"{len(items)} 个章节" if items else "未找到 section/subsection")

    def _emit_jump(self, row: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        line = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(line, int):
            self.jumpRequested.emit(line)


class HistoryPanel(QWidget):
    refreshRequested = Signal()
    restoreRequested = Signal(str)
    checkpointRequested = Signal()
    checkpointRestoreRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("historyPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        buttons = QHBoxLayout()
        self.refresh_button = QPushButton("刷新")
        self.restore_button = QPushButton("恢复")
        self.restore_button.setObjectName("primaryButton")
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.restore_button)
        layout.addLayout(buttons)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["时间", "类型", "大小"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.status_label = QLabel("未加载历史")
        self.status_label.setObjectName("panelHint")
        layout.addWidget(self.status_label)

        self.checkpoint_button = QPushButton("创建项目检查点…")
        self.checkpoint_restore_button = QPushButton("检查点恢复为新目录…")
        layout.addWidget(self.checkpoint_button)
        layout.addWidget(self.checkpoint_restore_button)
        self.checkpoint_button.clicked.connect(self.checkpointRequested.emit)
        self.checkpoint_restore_button.clicked.connect(self.checkpointRestoreRequested.emit)
        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.restore_button.clicked.connect(self._emit_restore)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._emit_restore())

    def set_snapshots(self, snapshots: list[HistorySnapshot], *, error: str = "") -> None:
        self.table.setRowCount(0)
        for snapshot in snapshots:
            row = self.table.rowCount()
            self.table.insertRow(row)
            time_item = QTableWidgetItem(snapshot.created_at.astimezone().strftime("%m-%d %H:%M"))
            time_item.setData(Qt.ItemDataRole.UserRole, str(snapshot.snapshot_path))
            self.table.setItem(row, 0, time_item)
            self.table.setItem(row, 1, QTableWidgetItem(snapshot.label))
            self.table.setItem(row, 2, QTableWidgetItem(f"{snapshot.size / 1024:.1f} KB"))
        self.status_label.setText(("历史不可用，原件保留：" + error) if error else (
            f"{len(snapshots)} 个文本快照（恢复时核对摘要）" if snapshots else "暂无文本快照"))
        self.status_label.setWordWrap(True)
        self.restore_button.setEnabled(bool(snapshots) and not error)

    def _emit_restore(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return
        snapshot_path = self.table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if isinstance(snapshot_path, str):
            self.restoreRequested.emit(snapshot_path)


class ProjectSearchPanel(QWidget):
    searchRequested = Signal(str, bool, bool)
    jumpRequested = Signal(str, int, int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("projectSearchPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索当前项目")
        self.search_button = QPushButton("搜索")
        row.addWidget(self.search_edit)
        row.addWidget(self.search_button)
        layout.addLayout(row)

        options = QHBoxLayout()
        self.case_checkbox = QCheckBox("区分大小写")
        self.whole_word_checkbox = QCheckBox("全词")
        options.addWidget(self.case_checkbox)
        options.addWidget(self.whole_word_checkbox)
        options.addStretch()
        layout.addLayout(options)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["文件", "行号", "内容"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.status_label = QLabel("未搜索")
        self.status_label.setObjectName("panelHint")
        layout.addWidget(self.status_label)

        self.search_button.clicked.connect(self._emit_search)
        self.search_edit.returnPressed.connect(self._emit_search)
        self.table.cellDoubleClicked.connect(lambda row, _column: self._emit_jump(row))

    def set_results(self, project_dir: Path, results: list[ProjectSearchResult]) -> None:
        self.table.setRowCount(0)
        for result in results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            try:
                label = result.file.relative_to(project_dir).as_posix()
            except ValueError:
                label = result.file.name
            file_item = QTableWidgetItem(label)
            file_item.setData(Qt.ItemDataRole.UserRole, str(result.file))
            file_item.setData(Qt.ItemDataRole.UserRole + 1, result.line)
            file_item.setData(Qt.ItemDataRole.UserRole + 2, result.column)
            self.table.setItem(row, 0, file_item)
            self.table.setItem(row, 1, QTableWidgetItem(str(result.line)))
            self.table.setItem(row, 2, QTableWidgetItem(result.excerpt))
        self.status_label.setText(f"{len(results)} 个结果" if results else "没有匹配")

    def _emit_search(self) -> None:
        self.searchRequested.emit(
            self.search_edit.text().strip(),
            self.case_checkbox.isChecked(),
            self.whole_word_checkbox.isChecked(),
        )

    def _emit_jump(self, row: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        line = item.data(Qt.ItemDataRole.UserRole + 1)
        column = item.data(Qt.ItemDataRole.UserRole + 2)
        if isinstance(path, str) and isinstance(line, int) and isinstance(column, int):
            self.jumpRequested.emit(path, line, column)


class ImagesPanel(QWidget):
    refreshRequested = Signal()
    insertRequested = Signal(str)
    checkRequested = Signal()
    cancelCheckRequested = Signal()
    locationRequested = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("imagesPanel")
        outer = QVBoxLayout(self)
        self.material_tabs = QTabWidget()
        outer.addWidget(self.material_tabs)
        inventory = QWidget()
        layout = QVBoxLayout(inventory)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        buttons = QHBoxLayout()
        self.refresh_button = QPushButton("刷新")
        self.insert_button = QPushButton("插入")
        self.insert_button.setObjectName("primaryButton")
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.insert_button)
        layout.addLayout(buttons)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["图片", "路径", "状态"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(54)
        self.table.setIconSize(_IMAGE_THUMBNAIL_SIZE)
        self._thumbnail_cache = _ImageThumbnailCache(
            max_entries=_IMAGE_THUMBNAIL_CACHE_LIMIT,
            target_size=self.table.iconSize(),
        )
        layout.addWidget(self.table)

        self.status_label = QLabel("未加载图片")
        self.status_label.setObjectName("panelHint")
        layout.addWidget(self.status_label)

        self.check_button = QPushButton("检查素材使用（只读）")
        self.check_button.clicked.connect(self.checkRequested.emit)
        layout.addWidget(self.check_button)
        self.material_tabs.addTab(inventory, "快捷浏览")
        health = QWidget()
        health_layout = QVBoxLayout(health)
        actions = QHBoxLayout()
        self.check_refresh_button = QPushButton("重新检查")
        self.check_refresh_button.clicked.connect(self.checkRequested.emit)
        self.check_cancel_button = QPushButton("取消")
        self.check_cancel_button.clicked.connect(self.cancelCheckRequested.emit)
        actions.addWidget(self.check_refresh_button)
        actions.addWidget(self.check_cancel_button)
        health_layout.addLayout(actions)
        self.check_status = QLabel()
        self.check_status.setWordWrap(True)
        health_layout.addWidget(self.check_status)
        self.health_table = QTableWidget(0, 2)
        self.health_table.setHorizontalHeaderLabels(["素材 / 引用", "状态"])
        self.health_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.health_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.health_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.health_table.verticalHeader().setVisible(False)
        self.health_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.health_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.health_table.itemSelectionChanged.connect(self._show_material_detail)
        health_layout.addWidget(self.health_table)
        self.check_detail = QPlainTextEdit()
        self.check_detail.setReadOnly(True)
        self.check_detail.setMinimumHeight(100)
        health_layout.addWidget(self.check_detail)
        self.check_locations = QListWidget()
        self.check_locations.itemActivated.connect(lambda _item: self._locate_material())
        health_layout.addWidget(self.check_locations)
        self.check_locate_button = QPushButton("定位所选引用位置")
        self.check_locate_button.clicked.connect(self._locate_material)
        health_layout.addWidget(self.check_locate_button)
        self.material_tabs.addTab(health, "使用检查")
        self.material_report = None
        self._material_scope = None
        self.set_usage_pending("尚未检查；不保存、不编译、不联网。")

        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.insert_button.clicked.connect(self._emit_insert)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._emit_insert())

    def set_assets(self, assets: list[ImageAsset]) -> None:
        self.table.setRowCount(0)
        for asset in assets:
            row = self.table.rowCount()
            self.table.insertRow(row)
            name_item = QTableWidgetItem(asset.path.name)
            name_item.setData(Qt.ItemDataRole.UserRole, asset.relative_path)
            icon = self._thumbnail_cache.icon_for(asset.path)
            if not icon.isNull():
                name_item.setIcon(icon)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(asset.relative_path))
            status = "使用待检查" if asset.used_count is None else f"{'已引用' if asset.used_count else '未引用'} ({asset.used_count})"
            self.table.setItem(row, 2, QTableWidgetItem(status))
        self.status_label.setText(f"{len(assets)} 张图片" if assets else "未找到图片资源")

    _MATERIAL_RULES = {
        "asset_present": "已找到引用位置", "asset_unused": "未见静态使用（建议）", "usage_unknown": "使用范围未知",
        "asset_changed": "内容有变化", "asset_missing": "引用文件缺失", "asset_candidate": "同内容候选",
        "asset_ambiguous": "多个候选", "asset_unknown": "素材状态未知", "source_unknown": "源码范围未知",
        "inputs_changed": "输入已变化",
    }
    _MATERIAL_STATES = {"info": "信息", "warning": "需核对", "fail": "需处理", "unknown": "未知", "suggestion": "建议"}

    def set_usage_pending(self, message, *, busy=False):
        self.material_report = None
        self.health_table.setRowCount(0)
        self.check_status.setText(message)
        self.check_detail.setPlainText(message)
        self.check_locations.clear()
        self.check_locate_button.setEnabled(False)
        self.check_cancel_button.setEnabled(busy)

    def set_material_report(self, report, scope, checked_at):
        self.material_report, self._material_scope = report, scope
        self.health_table.blockSignals(True)
        self.health_table.setRowCount(len(report.items))
        for row, item in enumerate(report.items):
            label = item.label[:512] or self._MATERIAL_RULES.get(item.rule, item.rule)
            for column, value in enumerate((label, self._MATERIAL_STATES.get(item.status, item.status))):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                self.health_table.setItem(row, column, cell)
        self.health_table.blockSignals(False)
        coverage = "已检查支持的静态路径" if report.complete else "存在未解析或不完整范围"
        self.check_status.setText(f"检查记录：{checked_at}\n{coverage}；位置数量不是 TeX 执行次数。")
        self.check_cancel_button.setEnabled(False)
        self.check_detail.setPlainText(f"输入身份：{report.input_id}\n选择素材查看说明和源码位置。")
        self.check_locations.clear()
        self.check_locate_button.setEnabled(False)
        if report.items:
            self.health_table.selectRow(0)

    def _show_material_detail(self):
        self.check_locations.clear()
        report, row = self.material_report, self.health_table.currentRow()
        if report is None or not 0 <= row < len(report.items):
            return
        item = report.items[row]
        title = self._MATERIAL_RULES.get(item.rule, item.rule)
        text = [f"{title} · {item.label[:2048]}", f"已发现的源码位置：{len(item.locations)} 处",
                "位置只按当前入口的受支持静态路径统计；未保存缓冲区替代相应磁盘源码。",
                "未使用仅为建议，不删除素材；同内容候选不证明移动，不自动改路径。"]
        if item.digest:
            text.append(f"本次内容 SHA-256：{item.digest}")
        if item.baseline:
            text.extend((f"本窗口上次可读记录：{item.baseline.observed_at}", f"此前 SHA-256：{item.baseline.digest}"))
        if item.candidates:
            text.append("候选：" + "、".join(path.relative_to(self._material_scope).as_posix() for path in item.candidates)[:2048])
        text.extend((f"技术记录：{item.message[:2048]}", f"输入身份：{report.input_id}",
                     "源码单文件 4 MiB、累计 32 MiB；素材单文件 64 MiB、累计 256 MiB。结束复核另有同额预算。",
                     "最多 2000 个输入/目录条目、10000 个静态引用；不展开任意宏，超限为未知。",
                     "这是可刷新、可失效的观察记录，不是冻结备份或图片格式有效性证明。"))
        self.check_detail.setPlainText("\n".join(text))
        modes = {path: kind for path, kind, _digest in report.sources}
        for location in item.locations:
            mode = "缓冲区" if modes.get(location.path) == "buffer" else "磁盘源码"
            self.check_locations.addItem(f"{location.path.relative_to(self._material_scope).as_posix()}:{location.line} · {mode}")
        self.check_locate_button.setEnabled(bool(item.locations))
        if item.locations:
            self.check_locations.setCurrentRow(0)

    def _locate_material(self):
        row, location = self.health_table.currentRow(), self.check_locations.currentRow()
        if self.material_report is not None and row >= 0 and location >= 0:
            self.locationRequested.emit(row, location)

    def _emit_insert(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return
        rel_path = self.table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        if isinstance(rel_path, str):
            self.insertRequested.emit(rel_path)


class LabelsPanel(QWidget):
    refreshRequested = Signal()
    referenceRequested = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("labelsPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.refresh_button = QPushButton("刷新")
        layout.addWidget(self.refresh_button)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["标签", "类型", "行号"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.status_label = QLabel("未加载标签")
        self.status_label.setObjectName("panelHint")
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        self.ref_button = QPushButton("ref")
        self.autoref_button = QPushButton("autoref")
        self.eqref_button = QPushButton("eqref")
        buttons.addWidget(self.ref_button)
        buttons.addWidget(self.autoref_button)
        buttons.addWidget(self.eqref_button)
        layout.addLayout(buttons)

        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.ref_button.clicked.connect(lambda: self._emit_reference("ref"))
        self.autoref_button.clicked.connect(lambda: self._emit_reference("autoref"))
        self.eqref_button.clicked.connect(lambda: self._emit_reference("eqref"))
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._emit_reference("ref"))

    def set_labels(self, labels: list[LabelInfo], duplicates: set[str], undefined: set[str]) -> None:
        self.table.setRowCount(0)
        for label in labels:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(label.name))
            self.table.setItem(row, 1, QTableWidgetItem(label.kind))
            self.table.setItem(row, 2, QTableWidgetItem(str(label.line)))
        parts = [f"{len(labels)} 个标签"]
        if duplicates:
            parts.append(f"重复：{', '.join(sorted(duplicates))}")
        if undefined:
            parts.append(f"未定义 refs：{', '.join(sorted(undefined))}")
        self.status_label.setText(" | ".join(parts))

    def _emit_reference(self, command: str) -> None:
        selected = self.table.selectedItems()
        if selected:
            self.referenceRequested.emit(selected[0].text(), command)
