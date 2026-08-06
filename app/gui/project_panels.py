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
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.history import HistorySnapshot
from app.core.image_assets import ImageAsset
from app.core.latex_insertions import all_templates
from app.core.latex_outline import OutlineItem
from app.core.project_search import ProjectSearchResult
from app.core.project_tools import BibEntrySpec, LabelInfo, ProjectInitSpec


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
        self.parent_edit = QLineEdit(str(Path.home()))
        self.name_edit = QLineEdit("LaTeX 项目")
        self.template_combo = QComboBox()
        for template in all_templates():
            self.template_combo.addItem(template.title, template.key)
        self._build()

    def values(self) -> ProjectInitSpec:
        return ProjectInitSpec(
            parent_dir=Path(self.parent_edit.text().strip() or str(Path.home())),
            project_name=self.name_edit.text().strip(),
            template_key=str(self.template_combo.currentData()),
        )

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("父文件夹", self._folder_row())
        form.addRow("项目名称", self.name_edit)
        form.addRow("模板", self.template_combo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("referencesPanel")
        layout = QVBoxLayout(self)
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
        undefined = undefined or set()
        if undefined:
            self.status_label.setText(f"未定义 citations：{', '.join(sorted(undefined))}")
        else:
            self.status_label.setText(f"{len(keys)} 条引用")

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

        self.refresh_button.clicked.connect(self.refreshRequested.emit)
        self.restore_button.clicked.connect(self._emit_restore)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._emit_restore())

    def set_snapshots(self, snapshots: list[HistorySnapshot]) -> None:
        self.table.setRowCount(0)
        for snapshot in snapshots:
            row = self.table.rowCount()
            self.table.insertRow(row)
            time_item = QTableWidgetItem(snapshot.created_at.astimezone().strftime("%m-%d %H:%M"))
            time_item.setData(Qt.ItemDataRole.UserRole, str(snapshot.snapshot_path))
            self.table.setItem(row, 0, time_item)
            self.table.setItem(row, 1, QTableWidgetItem(snapshot.label))
            self.table.setItem(row, 2, QTableWidgetItem(f"{snapshot.size / 1024:.1f} KB"))
        self.status_label.setText(f"{len(snapshots)} 个快照" if snapshots else "暂无快照")

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

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("imagesPanel")
        layout = QVBoxLayout(self)
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
            status = "已引用" if asset.used_count else "未引用"
            self.table.setItem(row, 2, QTableWidgetItem(f"{status} ({asset.used_count})"))
        self.status_label.setText(f"{len(assets)} 张图片" if assets else "未找到图片资源")

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
