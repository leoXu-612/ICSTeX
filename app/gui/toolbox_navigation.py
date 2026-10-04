from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.gui.icons import icon
from app.gui.theme import COLOR_ACCENT, COLOR_TEXT_MUTED


class ToolboxNavigation(QWidget):
    """Compact vertical navigation for the docked project tools."""

    currentChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("toolboxNavigation")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._labels: list[str] = []
        self._buttons: list[QToolButton] = []
        self._pages: list[QWidget] = []
        self._current_index = -1
        self.project_splitter: QSplitter | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.rail = QWidget()
        self.rail.setObjectName("toolboxRail")
        self.rail_layout = QVBoxLayout(self.rail)
        self.rail_layout.setContentsMargins(4, 6, 4, 6)
        self.rail_layout.setSpacing(2)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        # AX Toggle changes checked state without emitting clicked. Keep the
        # selected page synchronized for mouse, keyboard and accessible actions.
        self.group.idToggled.connect(lambda index, checked: self.setCurrentIndex(index) if checked else None)

        self.stack = QStackedWidget()
        self.stack.setObjectName("toolboxStack")
        self.rail_scroll = QScrollArea()
        self.rail_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.rail_scroll.setWidgetResizable(True)
        self.rail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.rail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.rail_scroll.setFixedWidth(72)
        self.rail_scroll.setWidget(self.rail)
        layout.addWidget(self.rail_scroll)
        layout.addWidget(self.stack, 1)

    def addTab(
        self,
        widget: QWidget,
        text: str,
        icon_name: str,
        tooltip: str = "",
        *,
        section_break: bool = False,
        section_title: str = "",
    ) -> int:
        if section_break and self._buttons:
            divider = QFrame()
            divider.setObjectName("toolboxDivider")
            divider.setFrameShape(QFrame.Shape.HLine)
            self.rail_layout.addWidget(divider)
        if section_title:
            title = QLabel(section_title)
            title.setObjectName("toolboxSectionLabel")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.rail_layout.addWidget(title)

        index = len(self._pages)
        self._pages.append(widget)
        self.stack.addWidget(widget)
        button = QToolButton()
        button.setObjectName("toolboxNavButton")
        button.setCheckable(True)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus if index == 0 else Qt.FocusPolicy.ClickFocus)
        button.setAutoExclusive(True)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIcon(icon(icon_name, COLOR_TEXT_MUTED, 18))
        button.setIconSize(QSize(18, 18))
        button.setText(text)
        button.setToolTip(tooltip or text)
        button.setMinimumWidth(0)
        button.setMinimumHeight(48)
        button.installEventFilter(self)
        self.group.addButton(button, index)
        button.toggled.connect(
            lambda checked, target=button, name=icon_name: target.setIcon(
                icon(name, COLOR_ACCENT if checked else COLOR_TEXT_MUTED, 18)
            )
        )
        self.rail_layout.addWidget(button)
        self._buttons.append(button)
        self._labels.append(text)
        if index == 0:
            self._current_index = 0
            button.setChecked(True)
            self.setFocusProxy(button)
        return index

    def combine_project_panels(self) -> None:
        """Install files/outline once; keep the nine logical tool identities."""
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setObjectName("projectOutlineSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        for index, title in enumerate(("项目文件", "章节大纲")):
            panel = self._pages[index]
            self.stack.removeWidget(panel)
            section = QWidget()
            section.setObjectName("projectNavigationSection")
            layout = QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            heading = QLabel(title)
            heading.setObjectName("workbenchPanelTitle")
            heading.setMargin(6)
            layout.addWidget(heading)
            layout.addWidget(panel, 1)
            panel.show()
            splitter.addWidget(section)
        splitter.setSizes([550, 450])
        self.stack.insertWidget(0, splitter)
        self.project_splitter = splitter
        self.stack.setCurrentWidget(splitter)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn and watched in self._buttons:
            self.rail_scroll.ensureWidgetVisible(watched)
        if (self.project_splitter is not None and watched in self._buttons[:2]
                and event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab
                and not event.modifiers()):
            # Both panels share one page. Tab enters the selected logical tool,
            # rather than always entering the file tree above the outline.
            index = self._buttons.index(watched)
            self.setCurrentIndex(index)
            self._pages[index].setFocus(Qt.FocusReason.TabFocusReason)
            return True
        return super().eventFilter(watched, event)

    def finish(self) -> None:
        self.rail_layout.addStretch(1)
        # Keep the rail's children at its position in the outer focus chain.
        # A live proxy would make setTabOrder substitute the selected button.
        self.setFocusProxy(None)
        previous = self
        for button in self._buttons:
            QWidget.setTabOrder(previous, button)
            previous = button
        if self._buttons:
            self.setFocusProxy(self._buttons[self.currentIndex()])

    def count(self) -> int:
        return len(self._pages)

    def currentIndex(self) -> int:
        return self._current_index

    def setCurrentIndex(self, index: int) -> None:
        if not 0 <= index < len(self._pages):
            return
        changed = index != self._current_index
        self._current_index = index
        page = self.project_splitter if self.project_splitter is not None and index < 2 else self._pages[index]
        self.stack.setCurrentWidget(page)
        self._buttons[index].setChecked(True)
        for position, button in enumerate(self._buttons):
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus if position == index else Qt.FocusPolicy.ClickFocus)
        self.setFocusProxy(self._buttons[index])
        if changed:
            self.currentChanged.emit(index)

    def currentWidget(self) -> QWidget | None:
        return self.widget(self._current_index)

    def widget(self, index: int) -> QWidget | None:
        return self._pages[index] if 0 <= index < len(self._pages) else None

    def tabText(self, index: int) -> str:
        return self._labels[index] if 0 <= index < len(self._labels) else ""

    def setTabToolTip(self, index: int, tooltip: str) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setToolTip(tooltip)

    def navigationButton(self, index: int) -> QToolButton | None:
        return self._buttons[index] if 0 <= index < len(self._buttons) else None
